import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
let checked=0;
for(const name of await fs.readdir(path.join(root,'charts'))){
  if(!name.endsWith('.html'))continue;
  const html=await fs.readFile(path.join(root,'charts',name),'utf8');
  for(const match of html.matchAll(/<script>([\s\S]*?)<\/script>/g))new Function(match[1]);
  checked++;
}
console.log(`All ${checked} HTML files passed JavaScript syntax compilation.`);
