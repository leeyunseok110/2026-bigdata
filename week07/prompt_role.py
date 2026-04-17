import ollama
reviews = [
    "재미있었어요! 연기도 훌륭!",
    "시간 낭비. 스토리 엉망",
    "그냥 그랬어요."
    "OST 좋지만 결말이 아쉬워요"

]

for review in reviews:
    response = ollama.chat(
        model = "gemma3:4b",
        messages=[
            {"role": "system", "content": "감성 분석 전문가. 긍정/부정/중립"},
            {"role": "user", "content": review}
        ]
    )
    print(f"리뷰: {review[:30]}")
    print(f"감성 분석 결과: {response['message']['content']}")
    # print(type(response))
    print('='*60)