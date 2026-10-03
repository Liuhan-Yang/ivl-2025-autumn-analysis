import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const data=JSON.parse(await fs.readFile(path.join(root,'Data/Expanded/intermediate/ivl_single_season_dataset.json'),'utf8'));
const wb=Workbook.create();
const summary=wb.worksheets.add('概览');
const frames=[['大场',data.matches],['赛前特征',data.features],['半局原始数据',data.small_games]];
const col=n=>{let s='';for(n++;n;n=Math.floor((n-1)/26))s=String.fromCharCode(65+(n-1)%26)+s;return s;};
const safe=v=>typeof v==='string'&&v.startsWith('=')?"'"+v:v;
const display={match_number:'大场序号',date:'日期',home:'主队',away:'客队',actual:'大场结果',elo_diff_scaled:'Elo差 / 400',smoothed_win_rate_diff:'历史胜率差',avg_point_margin_diff:'历史分差 / 10',recent5_margin_diff:'近五场分差 / 10',hunter_margin_diff:'监管分差 / 4',survivor_margin_diff:'求生分差 / 4',head_to_head_margin:'交锋分差 / 10'};
for(const [name,rows] of frames){
  const sheet=wb.worksheets.add(name),keys=Object.keys(rows[0]);
  const matrix=[keys.map(k=>name==='赛前特征'?(display[k]||k):k),...rows.map(r=>keys.map(k=>k==='date'||k==='日期'?new Date(r[k]+'T00:00:00Z'):safe(r[k])))];
  const used=sheet.getRangeByIndexes(0,0,matrix.length,keys.length);
  used.values=matrix;used.format.font={name:'Arial',size:10};used.format.rowHeight=22;used.format.columnWidth=17;used.format.verticalAlignment='center';
  const head=sheet.getRangeByIndexes(0,0,1,keys.length);
  head.format.fill='#253f63';head.format.font={name:'Arial',size:10,bold:true,color:'#ffffff'};head.format.rowHeight=44;head.format.wrapText=true;head.format.horizontalAlignment='center';
  for(let j=0;j<keys.length;j++){
    const range=sheet.getRangeByIndexes(1,j,rows.length,1);
    const key=keys[j];
    if(key==='date'||key==='日期'){range.setNumberFormat('yyyy-mm-dd');sheet.getRange(`${col(j)}1`).format.columnWidth=14;}
    else if(rows.some(r=>typeof r[key]==='number')){range.setNumberFormat(rows.some(r=>typeof r[key]==='number'&&!Number.isInteger(r[key]))?'0.000':'0');}
    else range.setNumberFormat('@');
    if(key==='小局唯一ID'){sheet.getRange(`${col(j)}1`).format.columnWidth=58;}
    if(key==='大场对阵'||key==='deciding_rule'){sheet.getRange(`${col(j)}1`).format.columnWidth=25;}
  }
  sheet.showGridLines=false;sheet.freezePanes.freezeRows(1);sheet.freezePanes.freezeColumns(name==='半局原始数据'?3:1);
  const t=sheet.tables.add(`A1:${col(keys.length-1)}${matrix.length}`,true,{'大场':'MatchesTable','赛前特征':'FeaturesTable','半局原始数据':'GamesTable'}[name]);
  t.showFilterButton=true;
}
summary.showGridLines=false;summary.tabColor='#253f63';
summary.getRange('A2').values=[['2025 IVL 秋季赛数据概览']];summary.getRange('A2').format.font={name:'Arial',size:15,bold:true};
summary.getRange('A4:B4').values=[['指标','值']];summary.getRange('A5:A13').values=[['半局记录'],['大场数'],['队伍数'],['主胜大场'],['客胜大场'],['平局或未决大场'],['半局监管胜'],['半局平局'],['半局求生胜']];
const n=data.matches.length+1,g=data.small_games.length+1;
const mk=Object.keys(data.matches[0]),gk=Object.keys(data.small_games[0]);
const target=col(mk.indexOf('target')),outcome=col(gk.indexOf('单局结果'));
summary.getRange('B5:B13').formulas=[
 [`=COUNTA('半局原始数据'!C2:C${g})`],[`=COUNTA('大场'!A2:A${n})`],
 [String('='+data.manifest.teams)],
 [`=COUNTIFS('大场'!${target}2:${target}${n},1)`],[`=COUNTIFS('大场'!${target}2:${target}${n},0)`],[`=COUNTIFS('大场'!${target}2:${target}${n},0.5)`],
 [`=COUNTIFS('半局原始数据'!${outcome}2:${outcome}${g},"监管胜")`],[`=COUNTIFS('半局原始数据'!${outcome}2:${outcome}${g},"平局")`],[`=COUNTIFS('半局原始数据'!${outcome}2:${outcome}${g},"求生胜")`]
];
summary.getRange('A15:B18').values=[['数据日期',data.manifest.date_min+' 至 '+data.manifest.date_max],['大场标签','回合胜数优先，再比较总分'],['口径差异场数',data.manifest.label_disagreements],['来源','Data/Data_details_All_games_details.csv']];
summary.getRange('A4:B18').format.font={name:'Arial',size:10};summary.getRange('A4:B18').format.rowHeight=26;
summary.getRange('A4:B4').format.fill='#253f63';summary.getRange('A4:B4').format.font={name:'Arial',size:10,bold:true,color:'#ffffff'};
summary.getRange('A4:A18').format.columnWidth=25;summary.getRange('B4:B18').format.columnWidth=50;
summary.getRange('B5:B13').setNumberFormat('0');
wb.recalculate();
const expected=[data.small_games.length,data.matches.length,data.manifest.teams,...[1,0,.5].map(t=>data.matches.filter(r=>r.target===t).length),...['监管胜','平局','求生胜'].map(t=>data.small_games.filter(r=>r['单局结果']===t).length)];
const actual=summary.getRange('B5:B13').values.flat();
if(actual.some((v,i)=>v!==expected[i]))throw Error('Summary reconciliation failed: '+JSON.stringify(actual));
console.log((await wb.inspect({kind:'table',range:'概览!A4:B13',include:'values,formulas',tableMaxRows:10,tableMaxCols:2,maxChars:1800})).ndjson);
console.log((await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!',options:{useRegex:true,maxResults:30},summary:'formula error scan',maxChars:1000})).ndjson);
const qa=path.join(root,'experiments/qa');await fs.mkdir(qa,{recursive:true});
for(const [name,range] of [['概览','A1:B18'],['大场','A1:J9'],['赛前特征','A1:L9'],['半局原始数据','A1:J9']]){
  const preview=await wb.render({sheetName:name,range,scale:1.5,format:'png'});
  await fs.writeFile(path.join(qa,name+'.png'),new Uint8Array(await preview.arrayBuffer()));
}
const output=await SpreadsheetFile.exportXlsx(wb);await output.save(path.join(root,'Data/Expanded/IVL_single_season_dataset.xlsx'));
console.log('Workbook exported; 486 raw records, 90 matches, 90 feature rows retained.');
