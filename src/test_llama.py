import ollama
import json

def load_tags(path="tags.txt"):
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]

def classify_card_text(card_text, allowed_tags):
    tags_text = "\n".join(allowed_tags)

    system_prompt = """
あなたはデュエル・マスターズのカード効果文を解析する「タグ分類器」です。

【ルール】
- 出力してよいタグは「タグ一覧」に含まれるもののみ
- 新しいタグを作らない
- 当てはまらない場合は []
- 出力は JSON配列のみ
- 説明・文章は禁止
"""

    user_prompt = f"""
【タグ一覧】
{tags_text}

【カード効果文】
{card_text}

該当するタグを JSON配列で出力してください。
"""

    res = ollama.chat(
        model="qwen2.5:7b",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        options={
            "temperature": 0
        }
    )

    content = res["message"]["content"].strip()

    try:
        tags = json.loads(content)
        return [t for t in tags if t in allowed_tags]
    except Exception:
        return []

if __name__ == "__main__":
    tags = load_tags()

    test_card_text = """
自分の山札からクリーチャーを1体手札に加える。
その後、山札をシャッフルする。
"""

    result = classify_card_text(test_card_text, tags)
    print(result)
