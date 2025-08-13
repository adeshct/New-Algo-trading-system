import os, joblib, datetime as dt, numpy as np, pandas as pd
from typing import Dict, List, Any
from pathlib import Path

from app.strategies.base import BaseStrategy
from app.services.logger import get_logger
from app.services.utils import (
    nearest_strike,
    weekly_option_symbol,
    get_previous_session_ohlc,
)
from app.services.feature_store import FeatureStore  # implements append/sync/load methods

from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC
from xgboost import XGBClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import StratifiedKFold
from sklearn.utils import resample

logger = get_logger(__name__)
MODEL_DIR = Path("app/models/cpr_meta")
MODEL_DIR.mkdir(parents=True, exist_ok=True)

class CPRMetaMLStrategy(BaseStrategy):
    """Production CPR Meta-Label Strategy with Probability-Calibrated Ensemble."""

    def __init__(self, name="CPR_Meta_ML", symbols=None, quantity=75, atm_offset=0):
        symbols = symbols or ["NIFTY 50"]
        super().__init__(name, symbols,min_data_points= 2)
        self.qty = quantity
        self.atm_offset = atm_offset

        self.models: Dict[str, Any] = {}
        self.calibrators: Dict[str, Any] = {}
        self.meta_model = None

        self._tick_buffer = []
        self._bar_buffer = pd.DataFrame()  # finished 5-min bars as a DataFrame
        self._last5m_bar_time = None  # last boundary -- timestamp

        self.model_paths = {
            "rf": MODEL_DIR / "rf.pkl",
            "xgb": MODEL_DIR / "xgb.pkl",
            "svm": MODEL_DIR / "svm.pkl",
            "lr": MODEL_DIR / "lr.pkl",
            "meta": MODEL_DIR / "meta.pkl",
        }
        logger.info("CPR Meta ML Strategy Initiated")
        self._load_or_warm_models()

    # PRIMARY SIGNAL + FEATURE LOGGING
    def generate_signals(self, market_data: Dict[str, pd.DataFrame]) -> List[Dict[str, Any]]:
        signals = []
        sym = self.symbols[0]
        df = market_data.get(sym)
        if df is None or len(df) < 2:
            return signals
        #logger.info("Calling previous session ohlc")
        prev_ohlc = get_previous_session_ohlc(df)
        #logger.info("Calling cpr levels")
        cpr_levels = self._compute_cpr(prev_ohlc)
        #logger.info("Done with CPR Levels")
        # Level lists in order from lowest to highest
        levels = ["s4", "s3", "s2", "s1", "bc", "tc", "r1", "r2", "r3", "r4"]
        level_values = [cpr_levels[lvl] for lvl in levels]

        # Map each level to its neighbors (for targets)
        level_index_map = {lvl: i for i, lvl in enumerate(levels)}

        bars = df.tail(2)
        prev_bar = bars.iloc[0]
        curr_bar = bars.iloc[1]
        prev_close = prev_bar["close"]
        curr_close = curr_bar["close"]
        bar_time = curr_bar.name

        signals_found = []

        # CE signals: from below to above any level except bc (don't buy CE at bc)
        for ix, level_key in enumerate(levels):
            level_val = cpr_levels[level_key]
            # Crossing up
            if prev_close < level_val <= curr_close:

                # Cannot set target for last level
                if ix+1 >= len(levels): continue
                target_level = levels[ix+1]
                target_price = cpr_levels[target_level]

                # Stoploss: after entry, if close crosses level_key from above to below (failed breakout)
                # This is checked after the trade is placed in the real trading logic (not here)

                signals_found.append({
                    "signal": "bull",
                    "opt_type": "CE",
                    "entry_price": curr_close,
                    "target": target_price,
                    "stoploss_level": level_key,
                    "stoploss_price": level_val,  # stoploss triggers if, after entry, close < level_val
                    "level_crossed": level_key,
                })

        # PE signals: from above to below any level except tc (don't buy PE at tc)
        for ix, level_key in enumerate(levels):
            level_val = cpr_levels[level_key]
            # Crossing down
            if prev_close > level_val >= curr_close:

                # Cannot set target for first level
                if ix-1 < 0: continue
                target_level = levels[ix-1]
                target_price = cpr_levels[target_level]

                # Stoploss: after entry, if close crosses level_key from below to above (failed breakdown)

                signals_found.append({
                    "signal": "bear",
                    "opt_type": "PE",
                    "entry_price": curr_close,
                    "target": target_price,
                    "stoploss_level": level_key,
                    "stoploss_price": level_val,   # stoploss triggers if, after entry, close > level_val
                    "level_crossed": level_key,
                })

        # ...rest of your feature/ML/signal assembly logic here (just use new target/stoploss/level values)...

        for sig in signals_found:
            entry_idx = df.index.get_loc(bar_time)
            #features = self._build_features(curr_bar.to_frame().T, cpr_levels, 0, df, timestamp=bar_time)
            features = self._build_features(
                row=curr_bar,
                prev_day_cpr=cpr_levels,
                bar_idx=entry_idx,
                df=df,
                timestamp=bar_time,
                level_crossed=sig["level_crossed"],
                signal_type=sig["signal"],
                target=sig["target"],
                stoploss=sig["stoploss_price"],
                cpr_width_label=sig.get("cpr_width_label"),
            )

            meta_feat = {
                "dt": bar_time,
                "direction": 1 if sig["signal"] == "bull" else 0,
                "entry_price": curr_close,
                "base_symbol": sym,
                "features": features,
                "label": None,
                "exit_time": None,
                "exit_price": None,
                "level_crossed": sig["level_crossed"],
                "target": sig["target"],
                "stoploss": sig["stoploss_price"],
            }
            FeatureStore.append("cpr_meta_signals", meta_feat, label=None)

            if not self._ml_ensemble_filter(features):
                logger.info("[%s] ML filter: REJECT (%s cross)", self.name, sig["level_crossed"])
                continue

            strike = nearest_strike(curr_close + self.atm_offset, 100)
            ##expiry = self.broker.get_next_expiry(sym)
            expiry = dt.date(2025,8,28)
            opt_symbol = weekly_option_symbol(sym, strike, sig["opt_type"], expiry)
            if sym == 'NIFTY':
                self.qty = 75
            elif sym == 'BANKNIFTY':
                self.qty = 35

            trade_signal = self._create_signal(
                symbol=opt_symbol,
                action="BUY",
                quantity=self.qty,
                price=0,
                signal_type=f"CPR_{('bull' if sig['opt_type'] == 'CE' else 'bear').upper()}_{sig['level_crossed'].upper()}",
                metadata={
                    "ml_feat": features,
                    "bias": sig["signal"],
                    "cpr_levels": cpr_levels,
                    "entry_price": curr_close,
                    "target": sig["target"],
                    "stoploss": sig["stoploss_price"],
                    "level_crossed": sig["level_crossed"],
                },
            )
            logger.info("[%s] Signal %s %s generated at %.2f (target %.2f, stop %.2f)", 
                        self.name, opt_symbol, sig["signal"], curr_close, sig["target"], sig["stoploss_price"])
            signals.append(trade_signal)

        return signals


    def _compute_cpr(self, ohlc) -> Dict[str, float]:
        """Frank Ochoa CPR (level 4) computation."""
        h, l, c = ohlc["high"], ohlc["low"], ohlc["close"]
        pivot = (h + l + c) / 3
        bc = (h + l) / 2
        tc = pivot * 2 - bc
        r1, s1 = 2 * pivot - l, 2 * pivot - h
        r2, s2 = pivot + (h - l), pivot - (h - l)
        r3, s3 = h + 2 * (pivot - l), l - 2 * (h - pivot)
        r4, s4 = r3 + (r2 - r1), s3 - (s1 - s2)
        width = abs(tc - bc)
        logger.info(f"pivot: {pivot} /n bc: {bc} /n tc: {tc}")
        logger.info(f"r1: {r1} /n r2: {r2} /n r3: {r3} /n r4: {r4}")
        logger.info(f"s1: {s1} /n s2: {s2} /n s3: {s3} /n s4: {s4}")
        return dict(pivot=pivot, tc=tc, bc=bc, r1=r1, r2=r2, r3=r3, r4=r4, s1=s1, s2=s2, s3=s3, s4=s4, width=width)

    # def _build_features(self, df: pd.DataFrame, lv: Dict[str, float]) -> List[float]:
    #     """Feature vector at entry time: price/vol/vola/timestamps/CPR stats."""
    #     close = df["close"].iloc[-1]
    #     vwap = (df["close"]*df["volume"]).rolling(20).sum().iloc[-1] / (df["volume"].rolling(20).sum().iloc[-1] + 1e-9)
    #     ret5 = (close - df["close"].iloc[-2]) / df["close"].iloc[-2]
    #     width_pct = lv["width"] / close
    #     hl_span = lv["r1"] - lv["s1"]
    #     min5_vol = df["volume"].iloc[-1]
    #     time_of_day = df.index[-1].hour * 60 + df.index[-1].minute
    #     # Features can be expanded as required (add OHLC percentiles, volatility, regime, etc.)
    #     return [
    #         close, vwap, ret5, width_pct, hl_span, min5_vol, time_of_day,
    #         lv["pivot"], lv["tc"], lv["bc"], lv["r1"], lv["r2"], lv["r3"], lv["r4"], lv["s1"], lv["s2"], lv["s3"], lv["s4"]
    #     ]

    def _build_features(
        self,
        row,                      # pd.Series (current 5m bar)
        prev_day_cpr,             # dict with CPR/SR levels from prev session
        bar_idx,                  # int: bar index in day's df
        df,                       # full day's DataFrame
        timestamp=None,
        level_crossed=None,
        signal_type=None,         # "bull"/"bear"
        target=None,
        stoploss=None,
        cpr_width_label=None
    ) -> list:
        """
        Compose an enriched feature vector at signal entry, for CPR meta model.
        - row: current bar (Series), as from DataFrame.iterrows() or df.iloc...
        - prev_day_cpr: CPR/SR levels dict
        - bar_idx: integer index in df
        - df: reference DataFrame for rolling features
        - timestamp: datetime for bar (defaults to row.name)
        - level_crossed: which CPR/SR level triggered entry (str)
        - signal_type: 'bull' or 'bear'
        - target, stoploss: float prices of those levels
        - cpr_width_label: "narrow"/"average"/"wide"
        """
        close = row["close"]
        vwap_win = min(bar_idx, 20)
        vwap = (
            (df["close"].iloc[bar_idx - vwap_win : bar_idx] * df["volume"].iloc[bar_idx - vwap_win : bar_idx]).sum() /
            (df["volume"].iloc[bar_idx - vwap_win : bar_idx].sum() + 1e-9)
        )
        if timestamp is None:
            timestamp = row.name
        timestamp = pd.to_datetime(timestamp)
        time_of_day = timestamp.hour * 60 + timestamp.minute

        cpr_width = prev_day_cpr["width"]
        width_pct = cpr_width / close
        all_levels = ["s4", "s3", "s2", "s1", "bc", "tc", "r1", "r2", "r3", "r4"]
        level_cross_index = all_levels.index(level_crossed) if (level_crossed in all_levels) else -1
        pct_to_target = abs((target - close) / close) if target is not None else 0
        pct_to_stop = abs((stoploss - close) / close) if stoploss is not None else 0
        width_label_map = {"narrow": 0, "average": 1, "wide": 2}
        width_label_num = width_label_map.get(cpr_width_label, -1)
        is_bull = 1 if signal_type == "bull" else 0

        return [
            close,                     # 0: Close price at entry
            vwap,                      # 1: Rolling VWAP at entry
            close - vwap,              # 2: Close minus VWAP
            prev_day_cpr["pivot"],     # 3: CPR pivot
            prev_day_cpr["tc"],        # 4: Top CPR
            prev_day_cpr["bc"],        # 5: Bottom CPR
            prev_day_cpr["r1"],        # 6: R1
            prev_day_cpr["r2"],        # 7: R2
            prev_day_cpr["r3"],        # 8: R3
            prev_day_cpr["r4"],        # 9: R4
            prev_day_cpr["s1"],        # 10: S1
            prev_day_cpr["s2"],        # 11: S2
            prev_day_cpr["s3"],        # 12: S3
            prev_day_cpr["s4"],        # 13: S4
            cpr_width,                 # 14: CPR width (abs)
            width_pct,                 # 15: CPR width as pct of price
            time_of_day,               # 16: Minutes since midnight
            is_bull,                   # 17: 1 if bullish signal, 0 if bearish
            level_cross_index,         # 18: Index of crossed CPR/SR level
            pct_to_target,             # 19: |% distance to target|
            pct_to_stop,               # 20: |% distance to stoploss|
            width_label_num,           # 21: CPR width regime, encoded (0=narrow, 1=avg, 2=wide)
            row["open"],               # 22: Open price of bar
            row["high"],               # 23: High price of bar
            row["low"],                # 24: Low price of bar
            row["close"],              # 25: Close price of bar (redundant, but explicit)
            row["volume"],             # 26: Bar volume
        ]


    # ──────────────── ML/ENSEMBLE/PROBABILITY FILTER ────────────────
    def _ml_ensemble_filter(self, features: List[float], threshold=0.6) -> bool:
        """Pass features through each base model and then meta-model; accept if high-conf."""
        if not (self.models and self.meta_model):
            return True  # No filter, default accept
        base_probs = np.array([
            self.calibrators["rf"].predict_proba([features])[0][1],
            self.calibrators["xgb"].predict_proba([features])[0][1],
            self.calibrators["svm"].predict_proba([features])[0][1],
            self.calibrators["lr"].predict_proba([features])[0][1],
        ])
        # Meta ensemble model gets base model probs as features
        final_prob = self.meta_model.predict_proba([base_probs])[0][1]
        logger.debug(f"ML ensemble probabilities: {base_probs}, final: {final_prob:.2f}")
        return final_prob >= threshold

    # ──────────────── TRAINING AND CALIBRATION (Nightly) ────────────────
    def nightly_train(self):
        """Retrain all meta-label models and final ensemble."""
        records = FeatureStore.load_all("cpr_meta_signals")
        df = pd.DataFrame(records)
        df = df.dropna(subset=["label"])
        if len(df) < 300:
            logger.info("Insufficient samples to (re)train meta classifier. Need 300+ labelled.")
            return

        feats = np.stack(df["features"].to_list())
        y = np.array(df["label"].values, dtype=int)

        # Class balancing (bootstrap if needed)
        if not 0.4 < y.mean() < 0.6:
            n = min(np.sum(y == 0), np.sum(y == 1))
            ix0 = np.where(y == 0)[0]
            ix1 = np.where(y == 1)[0]
            ix0, ix1 = resample(ix0, n_samples=n, replace=False), resample(ix1, n_samples=n, replace=False)
            ix = np.r_[ix0, ix1]
            feats, y = feats[ix], y[ix]

        # Split train/test and fit base models with calibration
        skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
        base_models, calibrators = {}, {}
        for name, model in [
            ("rf", RandomForestClassifier(n_estimators=100, max_depth=7)),
            ("xgb", XGBClassifier(n_estimators=150, max_depth=4, learning_rate=0.07)),
            ("svm", SVC(probability=True, C=2.0, kernel="rbf", gamma="scale")),
            ("lr", LogisticRegression(max_iter=1000)),
        ]:
            # Calibrate on OOF
            calibrator = CalibratedClassifierCV(model, method="isotonic", cv=3)
            calibrator.fit(feats, y)
            base_models[name] = model
            calibrators[name] = calibrator
            joblib.dump(calibrator, self.model_paths[name])
            logger.info(f"{self.name}: Model and calibration for {name} saved.")

        # Ensemble meta-model (inputs = four base calibrated probs)
        base_probs = np.column_stack([
            calibrators[n].predict_proba(feats)[:,1] for n in ["rf", "xgb", "svm", "lr"]
        ])
        meta_model = LogisticRegression(max_iter=1000)
        meta_model.fit(base_probs, y)
        joblib.dump(meta_model, self.model_paths["meta"])
        logger.info(f"{self.name}: Meta ensemble model saved.")

        self.models, self.calibrators, self.meta_model = base_models, calibrators, meta_model

    def _load_or_warm_models(self):
        self.models, self.calibrators, self.meta_model = {}, {}, None
        for name in ["rf", "xgb", "svm", "lr"]:
            p = self.model_paths[name]
            if p.exists():
                self.calibrators[name] = joblib.load(p)
        if self.model_paths["meta"].exists():
            self.meta_model = joblib.load(self.model_paths["meta"])
        if self.meta_model:
            logger.info(f"{self.name}: All ML models loaded and ready")
        else:
            logger.warning(f"{self.name}: ML models missing or not fit (yet)!")

    # POST-TRADE/PnL LABEL FEEDBACK
    def on_trade_complete(self, trade):
        """Update trade label (win/loss) and label signal history accordingly."""
        features = trade.metadata.get("ml_feat")
        # Label as 1 if trade is profitable (option buying reward >0, fast), else 0
        reached = 1 if trade.pnl > 0.1 * abs(trade.price) and trade.duration < 30 else 0  # example thresholds
        # Find and update the corresponding entry in FeatureStore
        FeatureStore.update_label("cpr_meta_signals", features, reached)
