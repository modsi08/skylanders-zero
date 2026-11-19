/* SPDX-License-Identifier: GPL-3.0-or-later */
'use strict';
// All catalogue indexing and figure-name matching runs on the user's browser.
class FigureCatalogue {
 constructor(document){
  this.records=new Map();this.characters=new Map();this.types=new Map();
  for(const row of document.figures){
   const key=row.character_id+':'+row.variant_id;
   if(this.records.has(key))throw Error('Duplicate catalogue identity: '+key);
   this.records.set(key,row);
   if(!this.characters.has(row.character_id))this.characters.set(row.character_id,row);
   if(!this.types.has(row.character_id))this.types.set(row.character_id,new Set());
   this.types.get(row.character_id).add(row.figure_type);
  }
 }
 lookup(identity){
  if(!identity||identity.error)return {name:'Unidentified figure',match:'unknown',notes:[identity?.error||'Use Identify figures to read this file.']};
  const c=identity.character_id,v=identity.variant_id;
  const exact=!identity.blank&&this.records.get(c+':'+v);
  if(exact)return {...exact,match:'exact',known_character:true,known_variant:true};
  const base=!identity.blank&&this.characters.get(c);
  return {character_id:c,variant_id:v,name:base?base.character_name:'Unknown figure',
   character_name:base?base.character_name:null,element:base?base.element:null,
   figure_type:base&&this.types.get(c).size===1?base.figure_type:'Unknown',
   variant_name:'Unknown variant',edition_game:null,abilities:[],
   match:base?'character_only':'unknown',known_character:!!base,known_variant:false,
   notes:[identity.blank?'Blank or erased figure header.':base?'Character known; variant not in catalogue.':'Character ID not in catalogue.']};
 }
 static header(buffer){
  const b=new Uint8Array(buffer);if(b.length<32)throw Error('Incomplete figure header');
  return {character_id:b[16]+256*b[17]+65536*b[18],variant_id:b[28]+256*b[29],
   blank:b.slice(0,32).every(v=>v===0)||b.slice(0,32).every(v=>v===255)};
 }
}
if(typeof module!=='undefined'&&module.exports)module.exports=FigureCatalogue;
else globalThis.FigureCatalogue=FigureCatalogue;
