const { readFileSync, writeFileSync } = require('fs');
const { marked } = require('marked');

const md = readFileSync('亿级架构实施方案.md', 'utf-8');
const html = `<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
  body { font-family: 'Microsoft YaHei', sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; font-size: 14px; line-height: 1.8; color: #333; }
  h1 { font-size: 24px; border-bottom: 2px solid #333; padding-bottom: 10px; }
  h2 { font-size: 20px; border-bottom: 1px solid #ddd; padding-bottom: 8px; margin-top: 30px; }
  h3 { font-size: 16px; margin-top: 20px; }
  table { border-collapse: collapse; width: 100%; margin: 16px 0; font-size: 13px; }
  th, td { border: 1px solid #ddd; padding: 8px 12px; text-align: left; }
  th { background: #f5f5f5; font-weight: 600; }
  code { background: #f0f0f0; padding: 2px 6px; border-radius: 3px; font-size: 13px; }
  pre { background: #f5f5f5; padding: 12px 16px; border-radius: 6px; overflow-x: auto; }
  pre code { background: none; padding: 0; }
  strong { color: #1a1a1a; }
</style></head><body>${marked.parse(md)}</body></html>`;
writeFileSync('亿级架构实施方案.html', html, 'utf-8');
console.log('HTML generated');
