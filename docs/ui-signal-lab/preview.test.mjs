import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile,access} from 'node:fs/promises';
import {initialAlarms,filteredAlarms,validCommand,archives,concepts} from './model.mjs';

test('species and status filters compose without including handled alarms',()=>{
 const list=initialAlarms();
 assert.equal(filteredAlarms(list,'new','白喉红臀鹎').length,1);
 assert.equal(filteredAlarms(list,'all','白喉红臀鹎').length,2);
 list.find(x=>x.id==='SG-013').status='ignored';
 assert.equal(filteredAlarms(list,'new','白喉红臀鹎').length,0);
 assert.equal(filteredAlarms(list,'all','白喉红臀鹎').length,2);
});
test('offline, busy, unknown modes and invalid durations cannot execute',()=>{
 for(const mode of ['both','infrared','acoustic'])for(const duration of [3,5,8])assert.equal(validCommand(mode,duration,true,false),true);
 assert.equal(validCommand('both',5,false,false),false);
 assert.equal(validCommand('both',5,true,true),false);
 assert.equal(validCommand('unknown',5,true,false),false);
 assert.equal(validCommand('both',0,true,false),false);
});
test('reset fixtures do not share mutable event state',()=>{
 const a=initialAlarms();a[0].status='handled';assert.equal(initialAlarms()[0].status,'new');
});
test('four independent concepts and archive media exist',async()=>{
 assert.equal(new Set(concepts.map(x=>x.id)).size,4);
 for(const file of new Set([...archives.map(a=>a.image),'assets/demo.webm']))await access(new URL(file,import.meta.url));
});
test('prototype never sends business API requests',async()=>{
 const code=await readFile(new URL('app.js',import.meta.url),'utf8');
 assert.doesNotMatch(code,/\bfetch\s*\(|XMLHttpRequest|\/api\//);
});
