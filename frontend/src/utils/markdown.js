export function escapeHtml(text) {
  const d = document.createElement('div')
  d.textContent = text
  return d.innerHTML
}

export function renderMarkdown(text) {
  let h = escapeHtml(text)
  h = h.replace(/```(\w*)\n?([\s\S]*?)```/g, '<pre><code>$2</code></pre>')
  h = h.replace(/`([^`]+)`/g, '<code>$1</code>')
  h = h.replace(/### (.+)/g, '<h3>$1</h3>')
  h = h.replace(/## (.+)/g, '<h2>$1</h2>')
  h = h.replace(/# (.+)/g, '<h1>$1</h1>')
  h = h.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  h = h.replace(/\n\n/g, '</p><p>')
  h = h.replace(/\n/g, '<br>')
  if (!h.startsWith('<')) h = '<p>' + h + '</p>'
  return h
}
