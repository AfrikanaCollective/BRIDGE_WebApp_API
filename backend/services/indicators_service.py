# backend/services/indicators_service.py
"""
Aggregation queries against patient_summary_viz for dashboard indicators.

Each method returns a serialisable dict whose 'bars' list drives a chart
directly — the frontend does no further arithmetic.
"""

import logging
from typing import Any, Dict

from clients.mongo_client import MongoClient
from config.settings import settings

logger = logging.getLogger(__name__)


class IndicatorsService:
    """Runs read-only aggregation pipelines against patient_summary_viz."""

    def __init__(
        self,
        mongo_client: MongoClient,
        db_name: str = settings.MONGODB_DB_NAME,
        viz_collection_name: str = settings.MONGODB_VIZ_COLLECTION,
    ):
        self.mongo = mongo_client
        self.db_name = db_name
        self.viz_collection_name = viz_collection_name
        logger.info(
            f"📈 IndicatorsService initialized: MongoDB({db_name}.{viz_collection_name})"
        )

    @property
    def collection(self):
        return self.mongo.client[self.db_name][self.viz_collection_name]

    @staticmethod
    def _pct(numerator: int, denominator: int) -> float:
        return round(numerator / denominator * 100, 1) if denominator else 0.0

    async def infection_overview(self) -> Dict[str, Any]:
        """
        Returns three infection indicators as percentages:
          bar 1 — % of all patients where has_sepsis is True
          bar 2 — % of all patients where infection_antibiotics is True
          bar 3 — % of antibiotic patients where has_sepsis is also True
        """
        pipeline = [
            {
                "$group": {
                    "_id": None,
                    "total": {"$sum": 1},
                    "has_sepsis_n": {
                        "$sum": {"$cond": [{"$eq": ["$has_sepsis", True]}, 1, 0]}
                    },
                    "antibiotics_n": {
                        "$sum": {"$cond": [{"$eq": ["$infection_antibiotics", True]}, 1, 0]}
                    },
                    "sepsis_and_antibiotics_n": {
                        "$sum": {
                            "$cond": [
                                {
                                    "$and": [
                                        {"$eq": ["$has_sepsis", True]},
                                        {"$eq": ["$infection_antibiotics", True]},
                                    ]
                                },
                                1,
                                0,
                            ]
                        }
                    },
                }
            }
        ]

        rows = await self.collection.aggregate(pipeline).to_list(1)
        if not rows:
            return {"total": 0, "bars": []}

        r = rows[0]
        total = r["total"]
        antibiotics_n = r["antibiotics_n"]

        return {
            "total": total,
            "bars": [
                {
                    "key": "has_sepsis",
                    "label": "Sepsis Prevalence",
                    "value": self._pct(r["has_sepsis_n"], total),
                },
                {
                    "key": "infection_antibiotics",
                    "label": "Antibiotic Treatment",
                    "value": self._pct(r["antibiotics_n"], total),
                },
                {
                    "key": "sepsis_given_antibiotics",
                    "label": "Sepsis of Antibiotic Patients",
                    "value": self._pct(r["sepsis_and_antibiotics_n"], antibiotics_n),
                },
            ],
        }