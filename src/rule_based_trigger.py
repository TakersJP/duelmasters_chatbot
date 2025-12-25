import re

# ==============================
# 1. tags.txt 読み込み
# ==============================
def load_tags(path="tags.txt"):
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


# ==============================
# 2. ルール定義（非・除去系）
# ==============================
RULES = [
    # --- 基本 ---
    ("S・トリガー", [r"S・トリガー"]),

    ("ドロー", [
        r"カードを\d+枚引く",
        r"カードを\d+枚まで引く",
        r"カードを\d+枚まで引き",
        r"\d+枚ドロー",
        r"カードを引く"
    ]),

    ("マナブースト", [
        r"マナゾーンに置く"
    ]),

    ("マナ回収", [
        r"マナゾーンから.*手札に加える"
    ]),

    ("墓地回収", [
        r"墓地から.*手札に加える"
    ]),

    ("墓地肥やし", [
        r"山札の上から\d+枚.*墓地に置く",
        r"山札の上から\d+枚.*墓地に加える"
    ]),

    # --- サーチ ---
    ("サーチ（カード対象）", [
        r"山札から.*手札に加える"
    ]),

    ("サーチ（クリーチャー対象）", [
        r"山札から.*クリーチャー.*手札に加える"
    ]),

    ("サーチ（呪文対象）", [
        r"山札から.*呪文.*手札に加える"
    ]),

    # --- 妨害 ---
    ("ハンデス", [
        r"相手の手札を.*捨てる",
        r"相手は.*手札を.*捨てる"
    ]),

    ("ランデス", [
        r"相手のマナゾーン.*墓地に置く"
    ]),

    # --- シールド ---
    ("シールド操作", [
        r"シールドを.*加える",
        r"シールドを.*墓地に置く",
        r"シールドを.*手札に加える"
    ]),

    # --- 特殊 ---
    ("コスト踏み倒し", [
        r"コストを支払わずに",
        r"支払わなくてもよい"
    ]),

    ("GR召喚", [
        r"GR召喚"
    ]),

    ("相手の山札を削る", [
        r"相手の山札の上から\d+枚.*墓地に置く"
    ]),

    ("対象（クリーチャー）", [
        r"クリーチャーを\d*体",
        r"クリーチャーを選ぶ"
    ]),
]


# ==============================
# 3. 除去系ルール（移動先別）
# ==============================
REMOVAL_RULES = [
    # --- 破壊 / 墓地送り ---
    ("破壊", [
        r"破壊する"
    ]),

    # --- バウンス ---
    ("バウンス", [
        r"手札に戻す",
        r"持ち主の手札に戻す"
    ]),

    # --- マナ送り ---
    ("マナ送り", [
        r"マナゾーンに置く"
    ]),

    # --- シールド化 ---
    ("シールド化", [
        r"シールド化する",
        r"シールドゾーンに加える"
    ]),

    # --- デッキバウンス ---
    ("デッキバウンス", [
        r"山札の上に置く",
        r"山札の下に置く",
        r"山札に加えてシャッフル"
    ]),

    # --- 超次元送り ---
    ("超次元送り", [
        r"超次元ゾーンに置く"
    ]),
]

NON_TARGET_REMOVAL_PATTERNS = [
    r"すべて",
    r"各",
    r"ランダムに"
]


# ==============================
# 4. 除去タグ検出
# ==============================
def detect_removal_tags(card_text, allowed_tags):
    found = set()

    for tag, patterns in REMOVAL_RULES:
        if tag not in allowed_tags:
            continue
        for pat in patterns:
            if re.search(pat, card_text):
                found.add(tag)
                break

    if any(re.search(p, card_text) for p in NON_TARGET_REMOVAL_PATTERNS):
        if "除去（対象を取らない）" in allowed_tags:
            found.add("除去（対象を取らない）")

    return found


# ==============================
# 5. メイン分類関数
# ==============================
def rule_based_tags(card_text, allowed_tags):
    found = set()

    for tag, patterns in RULES:
        if tag not in allowed_tags:
            continue
        for pat in patterns:
            if re.search(pat, card_text):
                found.add(tag)
                break

    found |= detect_removal_tags(card_text, allowed_tags)

    return sorted(found)


# ==============================
# 6. テスト実行
# ==============================
if __name__ == "__main__":
    allowed_tags = load_tags("tags.txt")

    test_card_text = """
"S・トリガー
相手のクリーチャーを１体マナゾーンに置く。"
"""

    tags = rule_based_tags(test_card_text, allowed_tags)
    print(tags)
