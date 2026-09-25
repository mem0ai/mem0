from mem0.utils.memory_attributes import (
    NEGATIVE_CONSTRAINT_BOOST_WEIGHT,
    get_constraint_boost,
    infer_memory_attributes,
    is_recommendation_query,
)


class TestInferMemoryAttributes:
    def test_negative_preference_is_constraint(self):
        attrs = infer_memory_attributes("User does not want Smash Arena recommended because it is too noisy")
        assert attrs == {"memory_type": "constraint", "polarity": "negative"}

    def test_positive_preference_is_preference(self):
        attrs = infer_memory_attributes("User prefers quiet badminton venues with wooden courts")
        assert attrs == {"memory_type": "preference", "polarity": "positive"}

    def test_plain_fact_is_neutral(self):
        attrs = infer_memory_attributes("User plays badminton every Saturday morning")
        assert attrs == {"memory_type": "fact", "polarity": "neutral"}

    def test_ambiguous_negation_is_not_constraint(self):
        attrs = infer_memory_attributes("User is not bothered by noisy badminton venues")
        assert attrs == {"memory_type": "fact", "polarity": "neutral"}


class TestConstraintBoost:
    def test_recommendation_query_detected(self):
        assert is_recommendation_query("Can you recommend a badminton venue?")

    def test_non_recommendation_query_not_detected(self):
        assert not is_recommendation_query("What sports does the user play?")

    def test_constraint_boost_only_for_recommendation_queries(self):
        payload = {"memory_type": "constraint", "polarity": "negative"}
        assert get_constraint_boost("recommend a venue", payload) == NEGATIVE_CONSTRAINT_BOOST_WEIGHT
        assert get_constraint_boost("what sports does the user play", payload) == 0.0

    def test_constraint_boost_ignores_positive_preferences(self):
        payload = {"memory_type": "preference", "polarity": "positive"}
        assert get_constraint_boost("recommend a venue", payload) == 0.0
