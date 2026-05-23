"""
D-013 Layer 3: Score Tracker — Signal Source Performance

Aggregates verification results by signal source to surface which concepts
actually produce alpha and which are noise.

Bad signals surface automatically — no manual grading needed.
"""
from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict
from typing import Any


class ScoreTracker:
    """Track signal source performance over time."""
    
    def __init__(self, store_path = None):
        if store_path is None:
            store_path = Path.home() / "spark-vault" / "projects" / "D-013" / "build" / "calibration" / "scores.json"
        self.store_path = Path(store_path) if isinstance(store_path, str) else store_path
        self.scores = self._load()
    
    def _load(self) -> dict:
        if self.store_path.exists():
            try:
                return json.loads(self.store_path.read_text())
            except (json.JSONDecodeError, OSError):
                pass
        return {"sources": {}, "total_verified": 0, "total_hits": 0}
    
    def _save(self):
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        self.store_path.write_text(json.dumps(self.scores, indent=2, default=str))
    
    def record(self, verification: dict):
        """Record a single thesis verification."""
        source = verification.get("signal_source", "unknown")
        hit = verification.get("hit", False)
        
        if source not in self.scores["sources"]:
            self.scores["sources"][source] = {
                "verified": 0,
                "hits": 0,
                "misses": 0,
                "accuracy": 0.0,
                "avg_magnitude_score": 0.0,
                "total_pct": 0.0,
                "avg_conviction": 0.0,
                "last_verified": None,
                "status": "COLD"
            }
        
        src = self.scores["sources"][source]
        src["verified"] += 1
        src["hits"] += 1 if hit else 0
        src["misses"] += 0 if hit else 1
        src["accuracy"] = round(src["hits"] / src["verified"], 3) if src["verified"] > 0 else 0.0
        src["avg_magnitude_score"] = round(
            (src["avg_magnitude_score"] * (src["verified"] - 1) + verification.get("magnitude_score", 0)) / src["verified"], 3
        )
        src["total_pct"] = round(src["total_pct"] + verification.get("pct_change", 0), 4)
        src["avg_conviction"] = round(
            (src["avg_conviction"] * (src["verified"] - 1) + verification.get("predicted_conviction", 0)) / src["verified"], 3
        )
        src["last_verified"] = verification.get("verified_at", "")
        src["status"] = self._classify_source(source, src)
        
        self.scores["total_verified"] += 1
        self.scores["total_hits"] += 1 if hit else 0
        
        self._save()
    
    def record_batch(self, verifications: list[dict]):
        """Record a batch of verifications."""
        for v in verifications:
            if "error" not in v:
                self.record(v)
    
    def _classify_source(self, source: str, data: dict) -> str:
        """Classify signal source health."""
        verified = data["verified"]
        accuracy = data["accuracy"]
        
        if verified < 5:
            return "COLD"  # Not enough data
        elif accuracy >= 0.65:
            return "HOT"   # Reliable alpha
        elif accuracy >= 0.50:
            return "WARM"  # Marginal
        elif accuracy >= 0.40:
            return "COLD"  # Below threshold
        else:
            return "DEAD"  # Worse than random
    
    def get_health_report(self) -> dict:
        """Generate signal source health report."""
        sources = []
        for name, data in self.scores["sources"].items():
            verified = data["verified"]
            accuracy = data["accuracy"]
            status = data["status"]
            
            # Conviction-weighted score (0-100)
            cw_score = round(accuracy * 100 * (data["avg_magnitude_score"] + 0.5), 1) if verified > 0 else 0
            
            sources.append({
                "source": name,
                "verified": verified,
                "accuracy": round(accuracy * 100, 1),
                "hits": data["hits"],
                "misses": data["misses"],
                "avg_magnitude": round(data["avg_magnitude_score"], 3),
                "avg_conviction": round(data["avg_conviction"], 1),
                "total_pct_return": round(data["total_pct"], 2),
                "conviction_weighted_score": cw_score,
                "status": status,
                "last_verified": data.get("last_verified", "")
            })
        
        sources.sort(key=lambda x: x["conviction_weighted_score"], reverse=True)
        
        total = self.scores["total_verified"]
        overall_accuracy = round(self.scores["total_hits"] / total * 100, 1) if total > 0 else 0
        
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_predictions": total,
            "total_hits": self.scores["total_hits"],
            "overall_accuracy": overall_accuracy,
            "active_sources": len(sources),
            "hot_sources": sum(1 for s in sources if s["status"] == "HOT"),
            "warm_sources": sum(1 for s in sources if s["status"] == "WARM"),
            "cold_sources": sum(1 for s in sources if s["status"] == "COLD"),
            "dead_sources": sum(1 for s in sources if s["status"] == "DEAD"),
            "sources": sources
        }
    
    def flag_dead_signals(self) -> list[str]:
        """Return signal sources that should be gated out."""
        report = self.get_health_report()
        return [s["source"] for s in report["sources"] if s["status"] == "DEAD" and s["verified"] >= 10]
    
    def apply_feedback(self) -> dict:
        """
        Apply feedback loop: adjust conviction weights based on signal health.
        
        Returns dict of source → weight_multiplier for use in thesis pipeline sizing.
        """
        weights = {}
        for name, data in self.scores["sources"].items():
            verified = data["verified"]
            accuracy = data["accuracy"]
            
            if verified < 5:
                weights[name] = 1.0  # Not enough data, neutral weight
            elif data["status"] == "HOT":
                weights[name] = min(1.3, 1.0 + (accuracy - 0.65) * 0.5)  # Boost up to 1.3x
            elif data["status"] == "WARM":
                weights[name] = 0.8  # Reduce to 80%
            elif data["status"] == "COLD":
                weights[name] = 0.5  # Reduce to 50%
            else:  # DEAD
                weights[name] = 0.0  # Gate out completely
        
        return weights
