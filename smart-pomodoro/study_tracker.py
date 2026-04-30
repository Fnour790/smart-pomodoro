"""
predictor.py
------------
Deux responsabilités :
  1. PomodoroPredictor  — utilise TimesFM (Google) pour prédire les prochaines
                          sessions de focus à partir de l'historique.
  2. ClaudeAdvisor      — envoie les stats + prédictions à l'API Claude pour
                          obtenir des conseils personnalisés.
"""

from __future__ import annotations

import os
from typing import Optional

# TimesFM : modèle de prévision de séries temporelles de Google
try:
    import timesfm
    TIMESFM_AVAILABLE = True
except ImportError:
    TIMESFM_AVAILABLE = False
    print("⚠️  TimesFM non installé. Utilisation du fallback statistique.")

# Anthropic SDK
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    print("⚠️  SDK Anthropic non installé. pip install anthropic")


# ===================================================================== #
#  1. PRÉDICTION TIMESFM
# ===================================================================== #

class PomodoroPredictor:
    """
    Prédit les minutes de focus pour les prochains jours
    à partir d'une série temporelle historique.

    Utilise TimesFM si disponible, sinon retombe sur une
    moyenne mobile pondérée (fallback déterministe).
    """

    def __init__(self, horizon: int = 7):
        """
        Args:
            horizon: Nombre de jours à prédire (défaut 7).
        """
        self.horizon = horizon
        self._model  = None

    def _load_model(self) -> None:
        """Charge le modèle TimesFM (lazy loading)."""
        if self._model is not None or not TIMESFM_AVAILABLE:
            return
        print("⏳ Chargement de TimesFM (première fois ~30s)...")
        self._model = timesfm.TimesFm(
            hparams=timesfm.TimesFmHparams(
                backend="torch",
                per_core_batch_size=32,
                horizon_len=self.horizon,
            ),
            checkpoint=timesfm.TimesFmCheckpoint(
                huggingface_repo_id="google/timesfm-1.0-200m-pytorch"
            ),
        )
        print("✅ TimesFM chargé.")

    def predict(self, time_series: list[float]) -> list[float]:
        """
        Prédit `horizon` valeurs futures à partir de la série.

        Args:
            time_series: Liste de minutes de focus par jour (ordre chronologique).

        Returns:
            Liste de `horizon` valeurs prédites (minutes/jour).
        """
        if len(time_series) < 7:
            return self._fallback(time_series)

        if TIMESFM_AVAILABLE:
            return self._predict_timesfm(time_series)
        return self._fallback(time_series)

    def _predict_timesfm(self, series: list[float]) -> list[float]:
        """Prédiction via TimesFM."""
        try:
            self._load_model()
            import numpy as np

            # TimesFM attend : liste de tableaux numpy, + longueurs de contexte
            forecast_input = [np.array(series, dtype=np.float32)]
            freq_input     = [0]   # 0 = fréquence non connue / journalière

            _, predictions = self._model.forecast(
                inputs=forecast_input,
                freq=freq_input,
            )
            # predictions[0] → tableau de shape (horizon,) ou (horizon, quantiles)
            preds = predictions[0]
            if hasattr(preds, "__len__") and len(preds.shape) > 1:
                preds = preds[:, 0]   # médiane (quantile 0.5)

            # Clamp : les minutes ne peuvent pas être négatives
            return [max(0.0, round(float(v), 1)) for v in preds[:self.horizon]]

        except Exception as e:
            print(f"⚠️  TimesFM error : {e} — fallback activé.")
            return self._fallback(series)

    def _fallback(self, series: list[float]) -> list[float]:
        """
        Fallback : moyenne mobile exponentielle (EMA) sur les 7 derniers jours.
        Simple, rapide, interprétable.
        """
        if not series:
            return [0.0] * self.horizon

        window = series[-min(14, len(series)):]
        alpha  = 0.3          # lissage EMA
        ema    = window[0]
        for v in window[1:]:
            ema = alpha * v + (1 - alpha) * ema

        # Légère tendance : +/- 5 % selon les 3 derniers jours vs EMA
        recent_avg = sum(window[-3:]) / min(3, len(window))
        trend      = (recent_avg - ema) / max(ema, 1) * 0.05

        predictions = []
        val = ema
        for _ in range(self.horizon):
            val = max(0.0, val * (1 + trend))
            predictions.append(round(val, 1))
        return predictions

    def format_predictions(
        self,
        predictions: list[float],
        start_label: str = "Demain",
    ) -> list[dict]:
        """
        Enrichit les prédictions brutes avec des labels et des niveaux.

        Returns:
            [{"day": "Demain", "minutes": 75.0, "formatted": "1h 15m", "level": "good"}, ...]
        """
        from datetime import datetime, timedelta

        result = []
        labels = [start_label] + [
            (datetime.now() + timedelta(days=i + 1)).strftime("%a %d/%m")
            for i in range(1, self.horizon)
        ]

        for i, (label, mins) in enumerate(zip(labels, predictions)):
            result.append({
                "day":       label,
                "minutes":   mins,
                "formatted": self._fmt_minutes(mins),
                "level":     self._level(mins),
            })
        return result

    @staticmethod
    def _fmt_minutes(m: float) -> str:
        h, mn = divmod(int(m), 60)
        return f"{h}h {mn:02d}m" if h else f"{mn}m"

    @staticmethod
    def _level(minutes: float) -> str:
        """Classe de productivité basée sur les minutes."""
        if minutes >= 120:  return "excellent"
        if minutes >= 75:   return "good"
        if minutes >= 40:   return "moderate"
        return "low"


# ===================================================================== #
#  2. CONSEILS CLAUDE
# ===================================================================== #

class ClaudeAdvisor:
    """
    Envoie les statistiques + prédictions TimesFM à l'API Claude
    pour obtenir des conseils de productivité personnalisés.
    """

    MODEL   = "claude-opus-4-5"
    MAX_TOKENS = 600

    SYSTEM_PROMPT = """Tu es un coach de productivité expert intégré dans une app Pomodoro.
Tu analyses les données de sessions de focus d'un utilisateur et tu fournis :
- Une analyse brève de ses habitudes (2-3 phrases)
- 2-3 conseils concrets et actionnables basés sur ses vraies données
- Une encouragement motivant personnalisé

Sois direct, bienveillant, et utilise les chiffres fournis dans ta réponse.
Réponds toujours en français. Maximum 200 mots."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Args:
            api_key: Clé API Anthropic. Si None, utilise ANTHROPIC_API_KEY env.
        """
        key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if ANTHROPIC_AVAILABLE and key:
            self.client = anthropic.Anthropic(api_key=key)
        else:
            self.client = None
            if not key:
                print("⚠️  ANTHROPIC_API_KEY non définie.")

    def get_advice(
        self,
        stats_summary: str,
        predictions: list[dict],
        user_question: Optional[str] = None,
    ) -> str:
        """
        Demande des conseils à Claude basés sur les stats + prédictions.

        Args:
            stats_summary:  Texte produit par StudyTracker.summary_for_claude().
            predictions:    Liste de dicts formatés par PomodoroPredictor.format_predictions().
            user_question:  Question optionnelle de l'utilisateur.

        Returns:
            Réponse textuelle de Claude.
        """
        if not self.client:
            return self._fallback_advice(stats_summary, predictions)

        pred_text = "\n".join(
            f"  {p['day']}: {p['formatted']} (niveau: {p['level']})"
            for p in predictions
        )

        user_msg = f"""{stats_summary}

=== Prédictions TimesFM pour les 7 prochains jours ===
{pred_text}

=== Question de l'utilisateur ===
{user_question or "Analyse mes données et donne-moi tes meilleurs conseils."}"""

        try:
            response = self.client.messages.create(
                model=self.MODEL,
                max_tokens=self.MAX_TOKENS,
                system=self.SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_msg}],
            )
            return response.content[0].text.strip()

        except anthropic.AuthenticationError:
            return "❌ Clé API Anthropic invalide. Vérifiez ANTHROPIC_API_KEY."
        except anthropic.RateLimitError:
            return "⏳ Limite de débit atteinte. Réessayez dans quelques secondes."
        except Exception as e:
            return f"❌ Erreur API Claude : {e}"

    @staticmethod
    def _fallback_advice(stats_summary: str, predictions: list[dict]) -> str:
        """Conseil générique si l'API n'est pas disponible."""
        avg_pred = sum(p["minutes"] for p in predictions) / max(len(predictions), 1)
        return (
            f"📊 Analyse locale (Claude non disponible)\n\n"
            f"Vos prédictions moyennes : {int(avg_pred)} min/jour la semaine prochaine.\n"
            f"Conseil : Maintenez des sessions régulières de 25 min avec 5 min de pause.\n"
            f"Essayez de travailler aux mêmes heures chaque jour pour ancrer l'habitude."
        )


# ===================================================================== #
#  Test rapide
# ===================================================================== #
if __name__ == "__main__":
    # Série simulée : 60 jours de données
    import random
    random.seed(42)
    series = [random.uniform(30, 120) for _ in range(60)]
    # Tendance haussière sur les 2 dernières semaines
    for i in range(46, 60):
        series[i] += 20

    predictor   = PomodoroPredictor(horizon=7)
    raw_preds   = predictor.predict(series)
    rich_preds  = predictor.format_predictions(raw_preds)

    print("=== Prédictions ===")
    for p in rich_preds:
        bar = "█" * int(p["minutes"] / 10)
        print(f"  {p['day']:15s} {p['formatted']:8s}  {bar}")

    # Test Claude (nécessite ANTHROPIC_API_KEY)
    stats_mock = """=== Résumé des sessions de focus ===
Aujourd'hui      : 1h 15m (3 sessions)
Cette semaine    : 6h 30m (18 sessions)
Moyenne/jour     : 55m
Streak actuel    : 5 jours"""

    advisor = ClaudeAdvisor()
    advice  = advisor.get_advice(stats_mock, rich_preds, "Comment améliorer mon streak ?")
    print("\n=== Conseils Claude ===")
    print(advice)