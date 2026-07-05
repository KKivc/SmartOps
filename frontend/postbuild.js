import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'fs'
import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const root = resolve(__dirname, '..')

// Read the built index.html
const htmlPath = resolve(root, 'static', 'index.html')
let html = readFileSync(htmlPath, 'utf-8')

// Wrap in Flask template: assets are served from /static/
html = html.replace(
  '</head>',
  '<meta name="csrf-token" content="{{ csrf_token() if csrf_token else "" }}">\n</head>'
)

// Write to Flask templates dir
const templateDir = resolve(root, 'templates')
if (!existsSync(templateDir)) mkdirSync(templateDir, { recursive: true })
writeFileSync(resolve(templateDir, 'index.html'), html, 'utf-8')

console.log('✅ Built index.html → templates/index.html')
