from mem0.utils.text_tokenization import contains_non_latin_letters, tokenize_for_bm25


def test_contains_non_latin_letters_ignores_latin_accents_and_numbers():
    assert contains_non_latin_letters("cafe naive resume") is False
    assert contains_non_latin_letters("café naïve résumé") is False
    assert contains_non_latin_letters("ＡＢＣ １２３") is False
    assert contains_non_latin_letters("EMP-123 2026") is False
    assert contains_non_latin_letters("员工 EMP-123") is True


def test_chinese_query_and_memory_share_partial_bm25_tokens():
    stored = set(tokenize_for_bm25("我喜欢喝榛子拿铁和年糕汤"))
    query = set(tokenize_for_bm25("榛子拿铁"))

    assert {"榛", "榛子", "拿铁"} <= (stored & query)


def test_japanese_and_korean_generate_overlapping_character_tokens():
    japanese = tokenize_for_bm25("東京で美味しいラーメンを食べた")
    korean = tokenize_for_bm25("서울에서 김치를 먹었다")

    assert "東京" in japanese
    assert "ラー" in japanese
    assert "서울" in korean
    assert "김치" in korean


def test_thai_output_is_not_empty():
    tokens = tokenize_for_bm25("ฉันชอบดื่มกาแฟในตอนเช้า")

    assert tokens
    assert len(tokens) > 3
    assert "ฉ" in tokens
    assert "ฉั" in tokens


def test_extended_cjk_and_hangul_jamo_generate_character_ngrams():
    cjk_extension_b = tokenize_for_bm25("𠀀𠀁")
    cjk_compatibility = tokenize_for_bm25("﨑塚")
    hangul_jamo = tokenize_for_bm25("한")
    hangul_syllable = tokenize_for_bm25("한")

    assert "𠀀" in cjk_extension_b
    assert "𠀀𠀁" in cjk_extension_b
    assert "﨑" in cjk_compatibility
    assert "塚" in cjk_compatibility
    assert "﨑塚" in cjk_compatibility
    assert "한" in hangul_jamo
    assert set(hangul_jamo) & set(hangul_syllable)


def test_spaced_non_latin_scripts_split_into_word_runs():
    arabic = tokenize_for_bm25("أحب شرب القهوة في الصباح")
    cyrillic = tokenize_for_bm25("Я люблю кофе утром")

    assert "أحب" in arabic
    assert "القهوة" in arabic
    assert "люблю" in cyrillic
    assert "кофе" in cyrillic


def test_mixed_identifiers_preserve_whole_and_parts():
    tokens = tokenize_for_bm25("员工 EMP-123 使用 sku_77")

    assert "emp-123" in tokens
    assert "emp" in tokens
    assert "123" in tokens
    assert "sku_77" in tokens
    assert "sku" in tokens
    assert "77" in tokens


def test_fullwidth_identifiers_normalize_to_ascii_tokens():
    fullwidth = set(tokenize_for_bm25("员工 ＥＭＰ－１２３ 使用 ｓｋｕ＿７７"))
    ascii_tokens = set(tokenize_for_bm25("EMP-123 sku_77"))

    assert {"emp-123", "emp", "123", "sku_77", "sku", "77"} <= fullwidth
    assert fullwidth & ascii_tokens


def test_halfwidth_katakana_normalizes_to_character_ngrams():
    halfwidth = set(tokenize_for_bm25("ｶﾀｶﾅ"))
    fullwidth = set(tokenize_for_bm25("カタカナ"))

    assert "カ" in halfwidth
    assert "カタ" in halfwidth
    assert {"カ", "カタ", "タカ", "カナ"} <= (halfwidth & fullwidth)


def test_repeated_cjk_tokens_are_not_deduplicated():
    tokens = tokenize_for_bm25("猫猫")

    assert tokens.count("猫") == 2
    assert "猫猫" in tokens
