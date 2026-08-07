"""Balanced v2 corpus generator: DEV and hidden TEST packs."""

import unittest

from benchmark.datasets.generator_v2 import (
    REQUIRED_KINDS,
    generate_personal,
    personal_test_pack,
)
from benchmark.validation import validate_corpus


class TestPersonalDevGenerator(unittest.TestCase):
    def test_generate_personal_is_deterministic_and_balanced(self):
        first = generate_personal(seed=20260805)
        second = generate_personal(seed=20260805)
        self.assertEqual(
            [event.to_dict() for event in first.events],
            [event.to_dict() for event in second.events],
        )
        self.assertEqual(len(first.queries), len(second.queries))
        kinds = {query.kind for query in first.queries}
        self.assertTrue(REQUIRED_KINDS.issubset(kinds), sorted(REQUIRED_KINDS - kinds))

    def test_generate_personal_passes_semantic_validation(self):
        corpus = generate_personal(seed=20260805)
        result = validate_corpus(corpus.events, corpus.queries, corpus.gold)
        self.assertTrue(result.passed, result.errors)

    def test_owner_subject_separation_and_lifecycle_ops(self):
        corpus = generate_personal(seed=20260805)
        upserts = [event for event in corpus.events if event.operation == "upsert"]
        self.assertTrue(all(event.principal == "user_001" for event in upserts))
        self.assertTrue(all(event.subject for event in upserts))
        deletes = [event for event in corpus.events if event.operation == "delete"]
        self.assertGreaterEqual(len(deletes), 2)
        self.assertTrue(all(event.target_event_id for event in deletes))

    def test_multi_hop_chain_complete_and_authority_respected(self):
        corpus = generate_personal(seed=20260805)
        multi = [q for q in corpus.queries if q.kind == "multi_hop"]
        self.assertEqual(len(multi), 1)
        self.assertGreaterEqual(len(corpus.gold[multi[0].query_id].gold_event_ids), 2)
        authority = [q for q in corpus.queries if q.kind == "authority_conflict"]
        self.assertGreaterEqual(len(authority), 1)
        gold_ids = corpus.gold[authority[0].query_id].gold_event_ids
        authorities = {e.authority for e in corpus.events if e.event_id in gold_ids}
        self.assertTrue(authorities <= {"user_explicit"})


class TestHiddenTestPacks(unittest.TestCase):
    def test_pack_is_balanced_and_deterministic(self):
        pack = personal_test_pack(seed=42, target=64, set_name="pack-1")
        self.assertEqual(len(pack.queries), 64)
        result = validate_corpus(pack.events, pack.queries, pack.gold)
        self.assertTrue(result.passed, result.errors)
        kinds = {query.kind for query in pack.queries}
        self.assertTrue(REQUIRED_KINDS.issubset(kinds), sorted(REQUIRED_KINDS - kinds))
        again = personal_test_pack(seed=42, target=64, set_name="pack-1")
        self.assertEqual(
            [query.query_id for query in pack.queries],
            [query.query_id for query in again.queries],
        )

    def test_pack_ids_are_namespaced_and_unique_across_packs(self):
        packs = [personal_test_pack(seed=100 + i, target=64, set_name=f"pack-{i + 1}") for i in range(3)]
        all_events = [event.event_id for pack in packs for event in pack.events]
        all_queries = [query.query_id for pack in packs for query in pack.queries]
        self.assertEqual(len(all_events), len(set(all_events)))
        self.assertEqual(len(all_queries), len(set(all_queries)))
        self.assertTrue(all(query.query_id.startswith("pack") for query in packs[0].queries))

    def test_test_values_are_disjoint_from_dev_values(self):
        dev = generate_personal(seed=20260805)
        dev_by_query = {query.query_id: query for query in dev.queries}
        dev_answers = {
            row.answer
            for query_id, row in dev.gold.items()
            if row.answer and dev_by_query[query_id].kind != "provenance"
        }
        for index in range(1, 4):
            pack = personal_test_pack(seed=200 + index, target=64, set_name=f"pack-{index}")
            pack_by_query = {query.query_id: query for query in pack.queries}
            pack_answers = {
                row.answer
                for query_id, row in pack.gold.items()
                if row.answer and pack_by_query[query_id].kind != "provenance"
            }
            self.assertEqual(dev_answers & pack_answers, set())
            for other in range(1, 4):
                if other == index:
                    continue
                other_pack = personal_test_pack(seed=200 + other, target=64, set_name=f"pack-{other}")
                other_by_query = {query.query_id: query for query in other_pack.queries}
                other_answers = {
                    row.answer
                    for query_id, row in other_pack.gold.items()
                    if row.answer and other_by_query[query_id].kind != "provenance"
                }
                self.assertEqual(pack_answers & other_answers, set())


if __name__ == "__main__":
    unittest.main()
