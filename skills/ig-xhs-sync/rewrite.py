import anthropic


SYSTEM_PROMPT = """You are a Chinese social media content writer specialising in 小红书 (Xiaohongshu/RedNote).

Given an Instagram caption (in any language), rewrite it as a 小红书 note following these rules:
- Write in natural, conversational Simplified Chinese
- Keep it SHORT — 1-3 sentences maximum
- Include 3-5 relevant emojis woven naturally into the text
- End with 5-8 hashtags in #话题 format on a new line
- If the input is empty or very short, produce a generic upbeat lifestyle note with emojis and hashtags

Output ONLY the rewritten note. No explanations, no English, no quotation marks."""


def rewrite_caption(caption: str, client: anthropic.Anthropic) -> str:
    """Rewrite an Instagram caption into XHS-native style using Claude API."""
    user_message = caption.strip() if caption.strip() else "[no caption provided]"

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )
    return response.content[0].text.strip()


def make_client(api_key: str) -> anthropic.Anthropic:
    """Create an Anthropic client from API key."""
    return anthropic.Anthropic(api_key=api_key)
