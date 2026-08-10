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

    async def psbi_diagnosis_overlap(self) -> Dict[str, Any]:
        """
        Computes all 8 combinations of the three suspected diagnoses and returns
        the count / % of patients in each region of the Venn diagram.

        Uses identical thresholds to psbi_suspected_diagnoses:
          Bacterial Sepsis     — sepsis_score  ≥ 3
          Pneumonia            — pneumonia_score ≥ 2
          Bacterial Meningitis — meningitis_score ≥ 2
        """
        def _bool(field: str) -> dict:
            return {"$eq": [f"${field}", True]}

        def _gt(field: str, v) -> dict:
            return {"$gt": [f"${field}", v]}

        def _lt(field: str, v) -> dict:
            return {"$lt": [f"${field}", v]}

        def _in(field: str, vals: list) -> dict:
            return {"$in": [f"${field}", vals]}

        def _or(*conds) -> dict:
            return {"$or": list(conds)}

        def _cond(condition: dict) -> dict:
            return {"$cond": [condition, 1, 0]}

        temp_abnormal = _or(
            _gt("temperature", 38),
            {"$and": [{"$ne": ["$temperature", None]}, _lt("temperature", 36)]},
        )

        pipeline = [
            {
                "$addFields": {
                    "sepsis_score": {"$add": [
                        _cond(temp_abnormal),
                        _cond(_or(_bool("is_floppy"), _bool("is_irritable"))),
                        _cond(_or(_bool("has_difficulty_feeding"), _in("cry", ["Weak/Absent", "Weak", "Absent"]))),
                        _cond(_or(_bool("has_apnoea"), _gt("respiratory_rate", 59))),
                        _cond(_or(_bool("has_central_cyanosis"), _gt("capillary_refill_in_seconds", 2), _in("skin", ["Mottling", "Pale"]))),
                    ]},
                    "pneumonia_score": {"$add": [
                        _cond(_gt("respiratory_rate", 59)),
                        _cond(_or(_bool("has_grunting"), _bool("chest_indrawing"))),
                        _cond(_bool("has_crackles")),
                        _cond(_or(_bool("has_central_cyanosis"), _lt("pulse_oximetry", 90))),
                        _cond(temp_abnormal),
                    ]},
                    "meningitis_score": {"$add": [
                        _cond(_bool("has_convulsions")),
                        _cond(_or(_bool("is_floppy"), _bool("is_irritable"))),
                        _cond(_bool("has_bulging_fontanelle")),
                        _cond(_bool("has_apnoea")),
                    ]},
                }
            },
            {
                "$addFields": {
                    "dx_s": {"$gte": ["$sepsis_score", 3]},
                    "dx_p": {"$gte": ["$pneumonia_score", 2]},
                    "dx_m": {"$gte": ["$meningitis_score", 2]},
                }
            },
            {
                "$group": {
                    "_id": {"s": "$dx_s", "p": "$dx_p", "m": "$dx_m"},
                    "count": {"$sum": 1},
                }
            },
            {
                "$group": {
                    "_id": None,
                    "total": {"$sum": "$count"},
                    "buckets": {"$push": {"combo": "$_id", "count": "$count"}},
                }
            },
        ]

        cursor = await self.collection.aggregate(pipeline)
        rows = await cursor.to_list(length=1)
        if not rows:
            return {"total": 0, "sets": {}}

        total = rows[0]["total"]
        bucket_map: Dict[tuple, int] = {}
        for b in rows[0]["buckets"]:
            c = b["combo"]
            bucket_map[(c["s"], c["p"], c["m"])] = b["count"]

        def region(s: bool, p: bool, m: bool) -> Dict[str, Any]:
            n = bucket_map.get((s, p, m), 0)
            return {"count": n, "pct": self._pct(n, total)}

        return {
            "total": total,
            "sets": {
                "sepsis_only":           region(True,  False, False),
                "pneumonia_only":         region(False, True,  False),
                "meningitis_only":        region(False, False, True),
                "sepsis_pneumonia":       region(True,  True,  False),
                "sepsis_meningitis":      region(True,  False, True),
                "pneumonia_meningitis":   region(False, True,  True),
                "all_three":              region(True,  True,  True),
                "none":                   region(False, False, False),
            },
        }

    async def psbi_suspected_diagnoses(self) -> Dict[str, Any]:
        """
        Estimates the proportion of patients meeting clinical case definitions
        for three pSBI suspected diagnoses.

        Bacterial Sepsis     — ≥ 3 of 5 criteria groups met
        Pneumonia            — ≥ 2 of 5 criteria groups met
        Bacterial Meningitis — ≥ 2 of 4 criteria groups met
        """
        def _bool(field: str) -> dict:
            return {"$eq": [f"${field}", True]}

        def _gt(field: str, v) -> dict:
            return {"$gt": [f"${field}", v]}

        def _lt(field: str, v) -> dict:
            return {"$lt": [f"${field}", v]}

        def _in(field: str, vals: list) -> dict:
            return {"$in": [f"${field}", vals]}

        def _or(*conds) -> dict:
            return {"$or": list(conds)}

        def _cond(condition: dict) -> dict:
            return {"$cond": [condition, 1, 0]}

        temp_abnormal = _or(
            _gt("temperature", 38),
            {"$and": [{"$ne": ["$temperature", None]}, _lt("temperature", 36)]},
        )

        sepsis_criteria = [
            _cond(temp_abnormal),
            _cond(_or(_bool("is_floppy"), _bool("is_irritable"))),
            _cond(_or(_bool("has_difficulty_feeding"), _in("cry", ["Weak/Absent", "Weak", "Absent"]))),
            _cond(_or(_bool("has_apnoea"), _gt("respiratory_rate", 59))),
            _cond(_or(_bool("has_central_cyanosis"), _gt("capillary_refill_in_seconds", 2), _in("skin", ["Mottling", "Pale"]))),
        ]

        pneumonia_criteria = [
            _cond(_gt("respiratory_rate", 59)),
            _cond(_or(_bool("has_grunting"), _bool("chest_indrawing"))),
            _cond(_bool("has_crackles")),
            _cond(_or(_bool("has_central_cyanosis"), _lt("pulse_oximetry", 90))),
            _cond(temp_abnormal),
        ]

        meningitis_criteria = [
            _cond(_bool("has_convulsions")),
            _cond(_or(_bool("is_floppy"), _bool("is_irritable"))),
            _cond(_bool("has_bulging_fontanelle")),
            _cond(_bool("has_apnoea")),
        ]

        pipeline = [
            {
                "$addFields": {
                    "sepsis_score": {"$add": sepsis_criteria},
                    "pneumonia_score": {"$add": pneumonia_criteria},
                    "meningitis_score": {"$add": meningitis_criteria},
                }
            },
            {
                "$group": {
                    "_id": None,
                    "total": {"$sum": 1},
                    "sepsis_n": {
                        "$sum": {"$cond": [{"$gte": ["$sepsis_score", 3]}, 1, 0]}
                    },
                    "pneumonia_n": {
                        "$sum": {"$cond": [{"$gte": ["$pneumonia_score", 2]}, 1, 0]}
                    },
                    "meningitis_n": {
                        "$sum": {"$cond": [{"$gte": ["$meningitis_score", 2]}, 1, 0]}
                    },
                }
            },
        ]

        cursor = await self.collection.aggregate(pipeline)
        rows = await cursor.to_list(length=1)
        if not rows:
            return {"total": 0, "bars": []}

        r = rows[0]
        total = r["total"]

        return {
            "total": total,
            "bars": [
                {
                    "key": "bacterial_sepsis",
                    "label": "Suspected bacterial sepsis",
                    "sublabel": "≥ 3 of 5 criteria groups met",
                    "value": self._pct(r["sepsis_n"], total),
                    "numerator": r["sepsis_n"],
                    "denominator": total,
                },
                {
                    "key": "pneumonia",
                    "label": "Suspected pneumonia",
                    "sublabel": "≥ 2 of 5 criteria groups met",
                    "value": self._pct(r["pneumonia_n"], total),
                    "numerator": r["pneumonia_n"],
                    "denominator": total,
                },
                {
                    "key": "bacterial_meningitis",
                    "label": "Suspected bacterial meningitis",
                    "sublabel": "≥ 2 of 4 criteria groups met",
                    "value": self._pct(r["meningitis_n"], total),
                    "numerator": r["meningitis_n"],
                    "denominator": total,
                },
            ],
        }

    async def psbi_sign_count_distribution(self) -> Dict[str, Any]:
        """
        For each patient, counts how many of the 16 unique pSBI signs/symptoms
        are present, then returns the distribution as % of total patients.

        Signs scored (deduplicated — has_apnoea listed twice in spec, counted once):
          1.  temperature > 38 or < 36
          2.  is_floppy = true
          3.  is_irritable = true
          4.  has_difficulty_feeding = true
          5.  cry in ["Weak/Absent", "Weak", "Absent"]
          6.  has_apnoea = true
          7.  respiratory_rate > 59
          8.  has_central_cyanosis = true
          9.  capillary_refill_in_seconds > 2
          10. skin in ["Mottling", "Pale"]
          11. has_grunting = true
          12. chest_indrawing = true
          13. has_crackles = true
          14. pulse_oximetry < 90
          15. has_convulsions = true
          16. has_bulging_fontanelle = true
        """
        def _bool_cond(field: str) -> dict:
            return {"$cond": [{"$eq": [f"${field}", True]}, 1, 0]}

        def _gt_cond(field: str, threshold) -> dict:
            return {"$cond": [{"$gt": [f"${field}", threshold]}, 1, 0]}

        def _lt_cond(field: str, threshold) -> dict:
            return {"$cond": [{"$lt": [f"${field}", threshold]}, 1, 0]}

        def _in_cond(field: str, values: list) -> dict:
            return {"$cond": [{"$in": [f"${field}", values]}, 1, 0]}

        pipeline = [
            {
                "$addFields": {
                    "psbi_score": {
                        "$add": [
                            {"$cond": [
                                {"$or": [
                                    {"$gt": ["$temperature", 38]},
                                    {"$and": [
                                        {"$ne": ["$temperature", None]},
                                        {"$lt": ["$temperature", 36]},
                                    ]},
                                ]},
                                1, 0,
                            ]},
                            _bool_cond("is_floppy"),
                            _bool_cond("is_irritable"),
                            _bool_cond("has_difficulty_feeding"),
                            _in_cond("cry", ["Weak/Absent", "Weak", "Absent"]),
                            _bool_cond("has_apnoea"),
                            _gt_cond("respiratory_rate", 59),
                            _bool_cond("has_central_cyanosis"),
                            _gt_cond("capillary_refill_in_seconds", 2),
                            _in_cond("skin", ["Mottling", "Pale"]),
                            _bool_cond("has_grunting"),
                            _bool_cond("chest_indrawing"),
                            _bool_cond("has_crackles"),
                            _lt_cond("pulse_oximetry", 90),
                            _bool_cond("has_convulsions"),
                            _bool_cond("has_bulging_fontanelle"),
                        ]
                    }
                }
            },
            {
                "$facet": {
                    "total": [{"$count": "n"}],
                    "distribution": [
                        {"$group": {"_id": "$psbi_score", "count": {"$sum": 1}}},
                        {"$sort": {"_id": 1}},
                    ],
                }
            },
        ]

        cursor = await self.collection.aggregate(pipeline)
        rows = await cursor.to_list(length=1)
        if not rows or not rows[0]["total"]:
            return {"total": 0, "bars": []}

        total = rows[0]["total"][0]["n"]
        distribution = rows[0]["distribution"]

        # Fill gaps so every integer from 0 to max score has a bucket
        dist_map = {d["_id"]: d["count"] for d in distribution}
        max_score = max(dist_map.keys(), default=0)

        bars = [
            {
                "count": i,
                "value": self._pct(dist_map.get(i, 0), total),
                "numerator": dist_map.get(i, 0),
                "denominator": total,
            }
            for i in range(max_score + 1)
        ]

        return {"total": total, "bars": bars}

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

        cursor = await self.collection.aggregate(pipeline)
        rows = await cursor.to_list(length=1)
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
                    "label": "% of patients with sepsis admission diagnosis",
                    "value": self._pct(r["has_sepsis_n"], total),
                    "numerator": r["has_sepsis_n"],
                    "denominator": total,
                },
                {
                    "key": "infection_antibiotics",
                    "label": "% patients given antibiotics at admission",
                    "value": self._pct(r["antibiotics_n"], total),
                    "numerator": r["antibiotics_n"],
                    "denominator": total,
                },
                {
                    "key": "sepsis_given_antibiotics",
                    "label": "% of patients given antibiotics at admission having sepsis admission diagnosis",
                    "value": self._pct(r["sepsis_and_antibiotics_n"], antibiotics_n),
                    "numerator": r["sepsis_and_antibiotics_n"],
                    "denominator": antibiotics_n,
                },
            ],
        }