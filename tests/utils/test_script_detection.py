from mem0.utils.script_detection import contains_non_latin_letters


class TestContainsNonLatinLetters:
    def test_empty_string(self):
        assert contains_non_latin_letters("") is False

    def test_pure_ascii(self):
        assert contains_non_latin_letters("John Smith works at Google") is False

    def test_latin_with_accents(self):
        # French, Spanish, German etc. must NOT trigger the warning.
        assert contains_non_latin_letters("café naïve résumé") is False
        assert contains_non_latin_letters("München Straße") is False
        assert contains_non_latin_letters("São Paulo") is False

    def test_digits_punctuation_only(self):
        # Strings with no letters at all shouldn't trigger either.
        assert contains_non_latin_letters("2024-Q1") is False
        assert contains_non_latin_letters("$100.00") is False
        assert contains_non_latin_letters("!!! ???") is False

    def test_chinese(self):
        assert contains_non_latin_letters("我喜欢喝咖啡") is True

    def test_japanese(self):
        assert contains_non_latin_letters("東京で美味しいラーメンを食べた") is True

    def test_korean(self):
        assert contains_non_latin_letters("서울에서 김치를 먹었다") is True

    def test_arabic(self):
        assert contains_non_latin_letters("أحب شرب القهوة") is True

    def test_thai(self):
        assert contains_non_latin_letters("ฉันชอบดื่มกาแฟ") is True

    def test_cyrillic(self):
        assert contains_non_latin_letters("Я люблю кофе") is True

    def test_mixed_script(self):
        # Mixed input with any non-Latin letter must return True.
        assert contains_non_latin_letters("I met 阿宁 at Google") is True
