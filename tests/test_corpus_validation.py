import unittest

from benchmark.corpus import generate_corpus
from benchmark.validation import validate_corpus


class TestCorpusValidation(unittest.TestCase):
    def test_generated_corpus_has_separate_owner_and_subject(self):
        corpus = generate_corpus(seed=21, n_persons=8, n_noise=2)
        normal = [e for e in corpus.events if e.operation == "upsert"]
        self.assertTrue(all(e.principal == "user_001" for e in normal))
        self.assertTrue(all(e.subject for e in normal))
        self.assertTrue(all(q.subject for q in corpus.queries if q.kind != "abstention"))

    def test_multi_hop_gold_contains_relationship_and_target_fact(self):
        corpus = generate_corpus(seed=21, n_persons=8, n_noise=2)
        query = next(q for q in corpus.queries if q.kind == "multi_hop")
        row = corpus.gold[query.query_id]
        kinds = {e.kind for e in corpus.events if e.event_id in row.gold_event_ids}
        self.assertEqual(kinds, {"relationship", "correction"})

    def test_deletion_commands_are_structured_and_not_scored_as_memory_text(self):
        corpus = generate_corpus(seed=21, n_persons=8, n_noise=2)
        lifecycle = [e for e in corpus.events if e.operation == "delete"]
        self.assertEqual(len(lifecycle), 2)
        self.assertTrue(all(e.target_event_id for e in lifecycle))
        self.assertTrue(all("do not remember" not in e.text.lower() for e in lifecycle))

    def test_generated_corpus_passes_schema_and_evidence_validation(self):
        corpus = generate_corpus(seed=21, n_persons=8, n_noise=2)
        result = validate_corpus(corpus.events, corpus.queries, corpus.gold)
        self.assertTrue(result.passed, result.errors)


if __name__ == "__main__":
    unittest.main()
