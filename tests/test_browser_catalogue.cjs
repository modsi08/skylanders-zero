// SPDX-License-Identifier: GPL-3.0-or-later
// Run with node tests/test_browser_catalogue.cjs. No npm dependencies required.
const assert=require('node:assert/strict');
const document=require('../catalog/figures.json');
const Catalogue=require('../static/catalogue.js');
const catalogue=new Catalogue(document);
for(const row of document.figures){
 const found=catalogue.lookup({character_id:row.character_id,variant_id:row.variant_id,blank:false});
 assert.equal(found.match,'exact');assert.equal(found.name,row.name);assert.equal(found.figure_type,row.figure_type);assert.equal(found.element,row.element);
}
const header=new Uint8Array(32);header[0]=1;header[16]=112;header[28]=6;header[29]=18;
assert.equal(catalogue.lookup(Catalogue.header(header)).name,'Tree Rex');
assert.equal(catalogue.lookup({character_id:112,variant_id:65535}).match,'character_only');
assert.equal(catalogue.lookup({character_id:540,variant_id:65535}).figure_type,'Unknown');
assert.equal(catalogue.lookup(Catalogue.header(new Uint8Array(32))).match,'unknown');
header[18]=1;assert.equal(Catalogue.header(header).character_id,65648);
assert.equal(catalogue.lookup(Catalogue.header(header)).match,'unknown');
assert.equal(catalogue.lookup({error:'Missing'}).match,'unknown');
assert.throws(()=>Catalogue.header(new Uint8Array(31)));
console.log('Browser catalogue lookup: all '+document.figures.length+' exact pairs and unknown/header cases passed.');
