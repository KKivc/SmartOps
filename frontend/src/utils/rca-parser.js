export function extractRcaReport(text) {
  // Try to match a JSON block within ```json ... ``` markers
  const jsonBlock = text.match(/```json\s*(\{[\s\S]*?"root_cause"[\s\S]*?\})\s*```/)
  if (jsonBlock) {
    try {
      const obj = JSON.parse(jsonBlock[1])
      if (obj.root_cause && obj.recommendation) return obj
    } catch { /* not valid JSON */ }
  }
  // Also try standalone JSON (no code block)
  try {
    const obj = JSON.parse(text)
    if (obj.root_cause && obj.recommendation) return obj
  } catch { /* not valid JSON */ }
  return null
}
