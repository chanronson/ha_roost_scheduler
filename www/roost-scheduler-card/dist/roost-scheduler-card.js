function e(e,t,i,s){var o,r=arguments.length,n=r<3?t:null===s?s=Object.getOwnPropertyDescriptor(t,i):s;if("object"==typeof Reflect&&"function"==typeof Reflect.decorate)n=Reflect.decorate(e,t,i,s);else for(var a=e.length-1;a>=0;a--)(o=e[a])&&(n=(r<3?o(n):r>3?o(t,i,n):o(t,i))||n);return r>3&&n&&Object.defineProperty(t,i,n),n}"function"==typeof SuppressedError&&SuppressedError;
/**
 * @license
 * Copyright 2019 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */
const t=window,i=t.ShadowRoot&&(void 0===t.ShadyCSS||t.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,s=Symbol(),o=new WeakMap;let r=class{constructor(e,t,i){if(this._$cssResult$=!0,i!==s)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=e,this.t=t}get styleSheet(){let e=this.o;const t=this.t;if(i&&void 0===e){const i=void 0!==t&&1===t.length;i&&(e=o.get(t)),void 0===e&&((this.o=e=new CSSStyleSheet).replaceSync(this.cssText),i&&o.set(t,e))}return e}toString(){return this.cssText}};const n=(e,...t)=>{const i=1===e.length?e[0]:t.reduce((t,i,s)=>t+(e=>{if(!0===e._$cssResult$)return e.cssText;if("number"==typeof e)return e;throw Error("Value passed to 'css' function must be a 'css' function result: "+e+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(i)+e[s+1],e[0]);return new r(i,e,s)},a=i?e=>e:e=>e instanceof CSSStyleSheet?(e=>{let t="";for(const i of e.cssRules)t+=i.cssText;return(e=>new r("string"==typeof e?e:e+"",void 0,s))(t)})(e):e;
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */var l;const d=window,c=d.trustedTypes,h=c?c.emptyScript:"",u=d.reactiveElementPolyfillSupport,p={toAttribute(e,t){switch(t){case Boolean:e=e?h:null;break;case Object:case Array:e=null==e?e:JSON.stringify(e)}return e},fromAttribute(e,t){let i=e;switch(t){case Boolean:i=null!==e;break;case Number:i=null===e?null:Number(e);break;case Object:case Array:try{i=JSON.parse(e)}catch(e){i=null}}return i}},g=(e,t)=>t!==e&&(t==t||e==e),v={attribute:!0,type:String,converter:p,reflect:!1,hasChanged:g},m="finalized";let f=class extends HTMLElement{constructor(){super(),this._$Ei=new Map,this.isUpdatePending=!1,this.hasUpdated=!1,this._$El=null,this._$Eu()}static addInitializer(e){var t;this.finalize(),(null!==(t=this.h)&&void 0!==t?t:this.h=[]).push(e)}static get observedAttributes(){this.finalize();const e=[];return this.elementProperties.forEach((t,i)=>{const s=this._$Ep(i,t);void 0!==s&&(this._$Ev.set(s,i),e.push(s))}),e}static createProperty(e,t=v){if(t.state&&(t.attribute=!1),this.finalize(),this.elementProperties.set(e,t),!t.noAccessor&&!this.prototype.hasOwnProperty(e)){const i="symbol"==typeof e?Symbol():"__"+e,s=this.getPropertyDescriptor(e,i,t);void 0!==s&&Object.defineProperty(this.prototype,e,s)}}static getPropertyDescriptor(e,t,i){return{get(){return this[t]},set(s){const o=this[e];this[t]=s,this.requestUpdate(e,o,i)},configurable:!0,enumerable:!0}}static getPropertyOptions(e){return this.elementProperties.get(e)||v}static finalize(){if(this.hasOwnProperty(m))return!1;this[m]=!0;const e=Object.getPrototypeOf(this);if(e.finalize(),void 0!==e.h&&(this.h=[...e.h]),this.elementProperties=new Map(e.elementProperties),this._$Ev=new Map,this.hasOwnProperty("properties")){const e=this.properties,t=[...Object.getOwnPropertyNames(e),...Object.getOwnPropertySymbols(e)];for(const i of t)this.createProperty(i,e[i])}return this.elementStyles=this.finalizeStyles(this.styles),!0}static finalizeStyles(e){const t=[];if(Array.isArray(e)){const i=new Set(e.flat(1/0).reverse());for(const e of i)t.unshift(a(e))}else void 0!==e&&t.push(a(e));return t}static _$Ep(e,t){const i=t.attribute;return!1===i?void 0:"string"==typeof i?i:"string"==typeof e?e.toLowerCase():void 0}_$Eu(){var e;this._$E_=new Promise(e=>this.enableUpdating=e),this._$AL=new Map,this._$Eg(),this.requestUpdate(),null===(e=this.constructor.h)||void 0===e||e.forEach(e=>e(this))}addController(e){var t,i;(null!==(t=this._$ES)&&void 0!==t?t:this._$ES=[]).push(e),void 0!==this.renderRoot&&this.isConnected&&(null===(i=e.hostConnected)||void 0===i||i.call(e))}removeController(e){var t;null===(t=this._$ES)||void 0===t||t.splice(this._$ES.indexOf(e)>>>0,1)}_$Eg(){this.constructor.elementProperties.forEach((e,t)=>{this.hasOwnProperty(t)&&(this._$Ei.set(t,this[t]),delete this[t])})}createRenderRoot(){var e;const s=null!==(e=this.shadowRoot)&&void 0!==e?e:this.attachShadow(this.constructor.shadowRootOptions);return((e,s)=>{i?e.adoptedStyleSheets=s.map(e=>e instanceof CSSStyleSheet?e:e.styleSheet):s.forEach(i=>{const s=document.createElement("style"),o=t.litNonce;void 0!==o&&s.setAttribute("nonce",o),s.textContent=i.cssText,e.appendChild(s)})})(s,this.constructor.elementStyles),s}connectedCallback(){var e;void 0===this.renderRoot&&(this.renderRoot=this.createRenderRoot()),this.enableUpdating(!0),null===(e=this._$ES)||void 0===e||e.forEach(e=>{var t;return null===(t=e.hostConnected)||void 0===t?void 0:t.call(e)})}enableUpdating(e){}disconnectedCallback(){var e;null===(e=this._$ES)||void 0===e||e.forEach(e=>{var t;return null===(t=e.hostDisconnected)||void 0===t?void 0:t.call(e)})}attributeChangedCallback(e,t,i){this._$AK(e,i)}_$EO(e,t,i=v){var s;const o=this.constructor._$Ep(e,i);if(void 0!==o&&!0===i.reflect){const r=(void 0!==(null===(s=i.converter)||void 0===s?void 0:s.toAttribute)?i.converter:p).toAttribute(t,i.type);this._$El=e,null==r?this.removeAttribute(o):this.setAttribute(o,r),this._$El=null}}_$AK(e,t){var i;const s=this.constructor,o=s._$Ev.get(e);if(void 0!==o&&this._$El!==o){const e=s.getPropertyOptions(o),r="function"==typeof e.converter?{fromAttribute:e.converter}:void 0!==(null===(i=e.converter)||void 0===i?void 0:i.fromAttribute)?e.converter:p;this._$El=o,this[o]=r.fromAttribute(t,e.type),this._$El=null}}requestUpdate(e,t,i){let s=!0;void 0!==e&&(((i=i||this.constructor.getPropertyOptions(e)).hasChanged||g)(this[e],t)?(this._$AL.has(e)||this._$AL.set(e,t),!0===i.reflect&&this._$El!==e&&(void 0===this._$EC&&(this._$EC=new Map),this._$EC.set(e,i))):s=!1),!this.isUpdatePending&&s&&(this._$E_=this._$Ej())}async _$Ej(){this.isUpdatePending=!0;try{await this._$E_}catch(e){Promise.reject(e)}const e=this.scheduleUpdate();return null!=e&&await e,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){var e;if(!this.isUpdatePending)return;this.hasUpdated,this._$Ei&&(this._$Ei.forEach((e,t)=>this[t]=e),this._$Ei=void 0);let t=!1;const i=this._$AL;try{t=this.shouldUpdate(i),t?(this.willUpdate(i),null===(e=this._$ES)||void 0===e||e.forEach(e=>{var t;return null===(t=e.hostUpdate)||void 0===t?void 0:t.call(e)}),this.update(i)):this._$Ek()}catch(e){throw t=!1,this._$Ek(),e}t&&this._$AE(i)}willUpdate(e){}_$AE(e){var t;null===(t=this._$ES)||void 0===t||t.forEach(e=>{var t;return null===(t=e.hostUpdated)||void 0===t?void 0:t.call(e)}),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(e)),this.updated(e)}_$Ek(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$E_}shouldUpdate(e){return!0}update(e){void 0!==this._$EC&&(this._$EC.forEach((e,t)=>this._$EO(t,this[t],e)),this._$EC=void 0),this._$Ek()}updated(e){}firstUpdated(e){}};
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */
var y;f[m]=!0,f.elementProperties=new Map,f.elementStyles=[],f.shadowRootOptions={mode:"open"},null==u||u({ReactiveElement:f}),(null!==(l=d.reactiveElementVersions)&&void 0!==l?l:d.reactiveElementVersions=[]).push("1.6.3");const x=window,$=x.trustedTypes,b=$?$.createPolicy("lit-html",{createHTML:e=>e}):void 0,_="$lit$",C=`lit$${(Math.random()+"").slice(9)}$`,w="?"+C,E=`<${w}>`,A=document,S=()=>A.createComment(""),k=e=>null===e||"object"!=typeof e&&"function"!=typeof e,V=Array.isArray,M="[ \t\n\f\r]",T=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,P=/-->/g,U=/>/g,N=RegExp(`>|${M}(?:([^\\s"'>=/]+)(${M}*=${M}*(?:[^ \t\n\f\r"'\`<>=]|("|')|))|$)`,"g"),D=/'/g,z=/"/g,R=/^(?:script|style|textarea|title)$/i,O=(e=>(t,...i)=>({_$litType$:e,strings:t,values:i}))(1),H=Symbol.for("lit-noChange"),j=Symbol.for("lit-nothing"),L=new WeakMap,I=A.createTreeWalker(A,129,null,!1);function B(e,t){if(!Array.isArray(e)||!e.hasOwnProperty("raw"))throw Error("invalid template strings array");return void 0!==b?b.createHTML(t):t}const F=(e,t)=>{const i=e.length-1,s=[];let o,r=2===t?"<svg>":"",n=T;for(let t=0;t<i;t++){const i=e[t];let a,l,d=-1,c=0;for(;c<i.length&&(n.lastIndex=c,l=n.exec(i),null!==l);)c=n.lastIndex,n===T?"!--"===l[1]?n=P:void 0!==l[1]?n=U:void 0!==l[2]?(R.test(l[2])&&(o=RegExp("</"+l[2],"g")),n=N):void 0!==l[3]&&(n=N):n===N?">"===l[0]?(n=null!=o?o:T,d=-1):void 0===l[1]?d=-2:(d=n.lastIndex-l[2].length,a=l[1],n=void 0===l[3]?N:'"'===l[3]?z:D):n===z||n===D?n=N:n===P||n===U?n=T:(n=N,o=void 0);const h=n===N&&e[t+1].startsWith("/>")?" ":"";r+=n===T?i+E:d>=0?(s.push(a),i.slice(0,d)+_+i.slice(d)+C+h):i+C+(-2===d?(s.push(void 0),t):h)}return[B(e,r+(e[i]||"<?>")+(2===t?"</svg>":"")),s]};class q{constructor({strings:e,_$litType$:t},i){let s;this.parts=[];let o=0,r=0;const n=e.length-1,a=this.parts,[l,d]=F(e,t);if(this.el=q.createElement(l,i),I.currentNode=this.el.content,2===t){const e=this.el.content,t=e.firstChild;t.remove(),e.append(...t.childNodes)}for(;null!==(s=I.nextNode())&&a.length<n;){if(1===s.nodeType){if(s.hasAttributes()){const e=[];for(const t of s.getAttributeNames())if(t.endsWith(_)||t.startsWith(C)){const i=d[r++];if(e.push(t),void 0!==i){const e=s.getAttribute(i.toLowerCase()+_).split(C),t=/([.?@])?(.*)/.exec(i);a.push({type:1,index:o,name:t[2],strings:e,ctor:"."===t[1]?X:"?"===t[1]?Z:"@"===t[1]?Q:J})}else a.push({type:6,index:o})}for(const t of e)s.removeAttribute(t)}if(R.test(s.tagName)){const e=s.textContent.split(C),t=e.length-1;if(t>0){s.textContent=$?$.emptyScript:"";for(let i=0;i<t;i++)s.append(e[i],S()),I.nextNode(),a.push({type:2,index:++o});s.append(e[t],S())}}}else if(8===s.nodeType)if(s.data===w)a.push({type:2,index:o});else{let e=-1;for(;-1!==(e=s.data.indexOf(C,e+1));)a.push({type:7,index:o}),e+=C.length-1}o++}}static createElement(e,t){const i=A.createElement("template");return i.innerHTML=e,i}}function G(e,t,i=e,s){var o,r,n,a;if(t===H)return t;let l=void 0!==s?null===(o=i._$Co)||void 0===o?void 0:o[s]:i._$Cl;const d=k(t)?void 0:t._$litDirective$;return(null==l?void 0:l.constructor)!==d&&(null===(r=null==l?void 0:l._$AO)||void 0===r||r.call(l,!1),void 0===d?l=void 0:(l=new d(e),l._$AT(e,i,s)),void 0!==s?(null!==(n=(a=i)._$Co)&&void 0!==n?n:a._$Co=[])[s]=l:i._$Cl=l),void 0!==l&&(t=G(e,l._$AS(e,t.values),l,s)),t}class W{constructor(e,t){this._$AV=[],this._$AN=void 0,this._$AD=e,this._$AM=t}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(e){var t;const{el:{content:i},parts:s}=this._$AD,o=(null!==(t=null==e?void 0:e.creationScope)&&void 0!==t?t:A).importNode(i,!0);I.currentNode=o;let r=I.nextNode(),n=0,a=0,l=s[0];for(;void 0!==l;){if(n===l.index){let t;2===l.type?t=new K(r,r.nextSibling,this,e):1===l.type?t=new l.ctor(r,l.name,l.strings,this,e):6===l.type&&(t=new ee(r,this,e)),this._$AV.push(t),l=s[++a]}n!==(null==l?void 0:l.index)&&(r=I.nextNode(),n++)}return I.currentNode=A,o}v(e){let t=0;for(const i of this._$AV)void 0!==i&&(void 0!==i.strings?(i._$AI(e,i,t),t+=i.strings.length-2):i._$AI(e[t])),t++}}class K{constructor(e,t,i,s){var o;this.type=2,this._$AH=j,this._$AN=void 0,this._$AA=e,this._$AB=t,this._$AM=i,this.options=s,this._$Cp=null===(o=null==s?void 0:s.isConnected)||void 0===o||o}get _$AU(){var e,t;return null!==(t=null===(e=this._$AM)||void 0===e?void 0:e._$AU)&&void 0!==t?t:this._$Cp}get parentNode(){let e=this._$AA.parentNode;const t=this._$AM;return void 0!==t&&11===(null==e?void 0:e.nodeType)&&(e=t.parentNode),e}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(e,t=this){e=G(this,e,t),k(e)?e===j||null==e||""===e?(this._$AH!==j&&this._$AR(),this._$AH=j):e!==this._$AH&&e!==H&&this._(e):void 0!==e._$litType$?this.g(e):void 0!==e.nodeType?this.$(e):(e=>V(e)||"function"==typeof(null==e?void 0:e[Symbol.iterator]))(e)?this.T(e):this._(e)}k(e){return this._$AA.parentNode.insertBefore(e,this._$AB)}$(e){this._$AH!==e&&(this._$AR(),this._$AH=this.k(e))}_(e){this._$AH!==j&&k(this._$AH)?this._$AA.nextSibling.data=e:this.$(A.createTextNode(e)),this._$AH=e}g(e){var t;const{values:i,_$litType$:s}=e,o="number"==typeof s?this._$AC(e):(void 0===s.el&&(s.el=q.createElement(B(s.h,s.h[0]),this.options)),s);if((null===(t=this._$AH)||void 0===t?void 0:t._$AD)===o)this._$AH.v(i);else{const e=new W(o,this),t=e.u(this.options);e.v(i),this.$(t),this._$AH=e}}_$AC(e){let t=L.get(e.strings);return void 0===t&&L.set(e.strings,t=new q(e)),t}T(e){V(this._$AH)||(this._$AH=[],this._$AR());const t=this._$AH;let i,s=0;for(const o of e)s===t.length?t.push(i=new K(this.k(S()),this.k(S()),this,this.options)):i=t[s],i._$AI(o),s++;s<t.length&&(this._$AR(i&&i._$AB.nextSibling,s),t.length=s)}_$AR(e=this._$AA.nextSibling,t){var i;for(null===(i=this._$AP)||void 0===i||i.call(this,!1,!0,t);e&&e!==this._$AB;){const t=e.nextSibling;e.remove(),e=t}}setConnected(e){var t;void 0===this._$AM&&(this._$Cp=e,null===(t=this._$AP)||void 0===t||t.call(this,e))}}class J{constructor(e,t,i,s,o){this.type=1,this._$AH=j,this._$AN=void 0,this.element=e,this.name=t,this._$AM=s,this.options=o,i.length>2||""!==i[0]||""!==i[1]?(this._$AH=Array(i.length-1).fill(new String),this.strings=i):this._$AH=j}get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}_$AI(e,t=this,i,s){const o=this.strings;let r=!1;if(void 0===o)e=G(this,e,t,0),r=!k(e)||e!==this._$AH&&e!==H,r&&(this._$AH=e);else{const s=e;let n,a;for(e=o[0],n=0;n<o.length-1;n++)a=G(this,s[i+n],t,n),a===H&&(a=this._$AH[n]),r||(r=!k(a)||a!==this._$AH[n]),a===j?e=j:e!==j&&(e+=(null!=a?a:"")+o[n+1]),this._$AH[n]=a}r&&!s&&this.j(e)}j(e){e===j?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,null!=e?e:"")}}class X extends J{constructor(){super(...arguments),this.type=3}j(e){this.element[this.name]=e===j?void 0:e}}const Y=$?$.emptyScript:"";class Z extends J{constructor(){super(...arguments),this.type=4}j(e){e&&e!==j?this.element.setAttribute(this.name,Y):this.element.removeAttribute(this.name)}}class Q extends J{constructor(e,t,i,s,o){super(e,t,i,s,o),this.type=5}_$AI(e,t=this){var i;if((e=null!==(i=G(this,e,t,0))&&void 0!==i?i:j)===H)return;const s=this._$AH,o=e===j&&s!==j||e.capture!==s.capture||e.once!==s.once||e.passive!==s.passive,r=e!==j&&(s===j||o);o&&this.element.removeEventListener(this.name,this,s),r&&this.element.addEventListener(this.name,this,e),this._$AH=e}handleEvent(e){var t,i;"function"==typeof this._$AH?this._$AH.call(null!==(i=null===(t=this.options)||void 0===t?void 0:t.host)&&void 0!==i?i:this.element,e):this._$AH.handleEvent(e)}}class ee{constructor(e,t,i){this.element=e,this.type=6,this._$AN=void 0,this._$AM=t,this.options=i}get _$AU(){return this._$AM._$AU}_$AI(e){G(this,e)}}const te=x.litHtmlPolyfillSupport;null==te||te(q,K),(null!==(y=x.litHtmlVersions)&&void 0!==y?y:x.litHtmlVersions=[]).push("2.8.0");
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */
var ie,se;class oe extends f{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){var e,t;const i=super.createRenderRoot();return null!==(e=(t=this.renderOptions).renderBefore)&&void 0!==e||(t.renderBefore=i.firstChild),i}update(e){const t=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(e),this._$Do=((e,t,i)=>{var s,o;const r=null!==(s=null==i?void 0:i.renderBefore)&&void 0!==s?s:t;let n=r._$litPart$;if(void 0===n){const e=null!==(o=null==i?void 0:i.renderBefore)&&void 0!==o?o:null;r._$litPart$=n=new K(t.insertBefore(S(),e),e,void 0,null!=i?i:{})}return n._$AI(e),n})(t,this.renderRoot,this.renderOptions)}connectedCallback(){var e;super.connectedCallback(),null===(e=this._$Do)||void 0===e||e.setConnected(!0)}disconnectedCallback(){var e;super.disconnectedCallback(),null===(e=this._$Do)||void 0===e||e.setConnected(!1)}render(){return H}}oe.finalized=!0,oe._$litElement$=!0,null===(ie=globalThis.litElementHydrateSupport)||void 0===ie||ie.call(globalThis,{LitElement:oe});const re=globalThis.litElementPolyfillSupport;null==re||re({LitElement:oe}),(null!==(se=globalThis.litElementVersions)&&void 0!==se?se:globalThis.litElementVersions=[]).push("3.3.3");
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */
const ne=e=>t=>"function"==typeof t?((e,t)=>(customElements.define(e,t),t))(e,t):((e,t)=>{const{kind:i,elements:s}=t;return{kind:i,elements:s,finisher(t){customElements.define(e,t)}}})(e,t),ae=(e,t)=>"method"===t.kind&&t.descriptor&&!("value"in t.descriptor)?{...t,finisher(i){i.createProperty(t.key,e)}}:{kind:"field",key:Symbol(),placement:"own",descriptor:{},originalKey:t.key,initializer(){"function"==typeof t.initializer&&(this[t.key]=t.initializer.call(this))},finisher(i){i.createProperty(t.key,e)}};
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */function le(e){return(t,i)=>void 0!==i?((e,t,i)=>{t.constructor.createProperty(i,e)})(e,t,i):ae(e,t)}
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */function de(e){return le({...e,state:!0})}
/**
 * @license
 * Copyright 2021 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */var ce;null===(ce=window.HTMLSlotElement)||void 0===ce||ce.prototype.assignedElements;let he=class extends oe{constructor(){super(...arguments),this.scheduleData={},this.currentMode="home",this.config={resolution_minutes:30,start_hour:0,end_hour:24,days:["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]},this.minValue=10,this.maxValue=30,this.gridCells=[],this.timeLabels=[],this.currentTime=new Date,this.isDragging=!1,this.dragStartCell=null,this.dragEndCell=null,this.selectedCells=new Set,this.editingValue=null,this.showValueEditor=!1,this.editorPosition={x:0,y:0},this.handleMouseMove=e=>{if(!this.isDragging||!this.dragStartCell)return;const t=this.getCellFromMouseEvent(e);t&&(this.dragEndCell=t,this.updateSelectedCells())},this.handleMouseUp=e=>{this.isDragging&&(this.isDragging=!1,document.removeEventListener("mousemove",this.handleMouseMove),document.removeEventListener("mouseup",this.handleMouseUp),this.selectedCells.size>0&&(this.showValueEditor=!0,this.editorPosition={x:e.clientX,y:e.clientY},this.editingValue=this.getAverageValueFromSelection()))}}connectedCallback(){super.connectedCallback(),this.updateCurrentTime(),setInterval(()=>this.updateCurrentTime(),6e4)}willUpdate(e){(e.has("scheduleData")||e.has("config")||e.has("currentMode"))&&this.generateGrid()}updateCurrentTime(){this.currentTime=new Date,this.requestUpdate()}generateGrid(){const{resolution_minutes:e,start_hour:t,end_hour:i,days:s}=this.config;this.timeLabels=[];const o=60*(i-t);for(let i=0;i<o;i+=e){const e=Math.floor(i/60)+t,s=i%60;this.timeLabels.push(`${e.toString().padStart(2,"0")}:${s.toString().padStart(2,"0")}`)}this.gridCells=s.map(e=>this.timeLabels.map(t=>{const i=this.getValueForSlot(e,t),s=this.isCurrentTimeSlot(e,t);return{day:e,time:t,value:i,isActive:null!==i,isCurrentTime:s}}))}getValueForSlot(e,t){const i=this.scheduleData[this.currentMode];if(!i||!i[e])return null;const s=i[e],o=this.timeToMinutes(t);for(const e of s){const t=this.timeToMinutes(e.start_time),i=this.timeToMinutes(e.end_time);if(o>=t&&o<i)return e.target_value}return null}isCurrentTimeSlot(e,t){const i=this.currentTime,s=this.getDayName(i.getDay()),o=60*i.getHours()+i.getMinutes(),r=this.timeToMinutes(t),n=r+this.config.resolution_minutes;return e===s&&o>=r&&o<n}timeToMinutes(e){const[t,i]=e.split(":").map(Number);return 60*t+i}getDayName(e){return["sunday","monday","tuesday","wednesday","thursday","friday","saturday"][e]}getValueColor(e){if(null===e)return"transparent";const t=(e-this.minValue)/(this.maxValue-this.minValue);return`hsl(${240*(1-Math.max(0,Math.min(1,t)))}, 70%, 50%)`}formatValue(e){return null===e?"":`${e}°`}render(){return this.gridCells.length&&Object.keys(this.scheduleData).length?O`
      <div class="grid-container">
        <!-- Mode selector -->
        <div class="mode-selector">
          ${Object.keys(this.scheduleData).map(e=>O`
            <button 
              class="mode-button ${e===this.currentMode?"active":""}"
              @click=${()=>this.selectMode(e)}
            >
              ${e.charAt(0).toUpperCase()+e.slice(1)}
            </button>
          `)}
        </div>

        <!-- Grid -->
        <div class="schedule-grid">
          <!-- Time header -->
          <div class="time-header">
            <div class="day-label"></div>
            ${this.timeLabels.map(e=>O`
              <div class="time-label">${e}</div>
            `)}
          </div>

          <!-- Grid rows -->
          ${this.config.days.map((e,t)=>O`
            <div class="grid-row">
              <div class="day-label">${e.charAt(0).toUpperCase()+e.slice(1)}</div>
              ${this.gridCells[t]?.map((e,i)=>{const s=`${t}-${i}`,o=this.selectedCells.has(s);return O`
                  <div 
                    class="grid-cell ${e.isActive?"active":""} ${e.isCurrentTime?"current-time":""} ${o?"selected":""}"
                    style="background-color: ${this.getValueColor(e.value)}"
                    title="${e.day} ${e.time}${e.value?` - ${this.formatValue(e.value)}`:""}"
                    data-day-index="${t}"
                    data-time-index="${i}"
                    @mousedown=${e=>this.handleCellMouseDown(e,t,i)}
                    @click=${e=>this.handleCellClick(e,t,i)}
                  >
                    ${e.isActive?this.formatValue(e.value):""}
                  </div>
                `})||[]}
            </div>
          `)}
        </div>

        <!-- Value Editor -->
        ${this.showValueEditor?O`
          <div class="value-editor-overlay" @click=${this.closeValueEditor}>
            <div 
              class="value-editor"
              style="left: ${this.editorPosition.x}px; top: ${this.editorPosition.y}px"
              @click=${e=>e.stopPropagation()}
              @keydown=${this.handleKeyDown}
            >
              <div class="editor-header">
                <span>Set Temperature</span>
                <button class="close-btn" @click=${this.closeValueEditor}>×</button>
              </div>
              <div class="editor-content">
                <div class="value-input-group">
                  <input
                    type="number"
                    .value=${this.editingValue?.toString()||""}
                    @input=${this.handleValueChange}
                    min=${this.minValue}
                    max=${this.maxValue}
                    step="0.5"
                    class="value-input"
                    placeholder="Temperature"
                    autofocus
                  />
                  <span class="unit">°C</span>
                </div>
                <div class="range-info">
                  Range: ${this.minValue}° - ${this.maxValue}°
                </div>
                <div class="selection-info">
                  ${this.selectedCells.size} cell${1!==this.selectedCells.size?"s":""} selected
                </div>
                <div class="editor-actions">
                  <button class="cancel-btn" @click=${this.closeValueEditor}>Cancel</button>
                  <button 
                    class="apply-btn" 
                    @click=${this.applyValueToSelection}
                    ?disabled=${null===this.editingValue||this.editingValue<this.minValue||this.editingValue>this.maxValue}
                  >
                    Apply
                  </button>
                </div>
              </div>
            </div>
          </div>
        `:""}

        <!-- Legend -->
        <div class="legend">
          <div class="legend-item">
            <div class="legend-color current-time-indicator"></div>
            <span>Current Time</span>
          </div>
          <div class="legend-item">
            <div class="legend-gradient">
              <div class="gradient-bar"></div>
              <div class="gradient-labels">
                <span>${this.minValue}°</span>
                <span>${this.maxValue}°</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    `:O`
        <div class="grid-loading">
          <p>Generating schedule grid...</p>
        </div>
      `}selectMode(e){this.currentMode=e,this.dispatchEvent(new CustomEvent("mode-changed",{detail:{mode:e},bubbles:!0,composed:!0}))}handleCellMouseDown(e,t,i){e.preventDefault(),this.isDragging=!0,this.dragStartCell={day:t,time:i},this.dragEndCell={day:t,time:i},this.updateSelectedCells(),document.addEventListener("mousemove",this.handleMouseMove),document.addEventListener("mouseup",this.handleMouseUp)}getCellFromMouseEvent(e){if("function"!=typeof document.elementFromPoint)return null;const t=document.elementFromPoint(e.clientX,e.clientY);if(!t||!t.classList.contains("grid-cell"))return null;const i=parseInt(t.getAttribute("data-day-index")||"-1"),s=parseInt(t.getAttribute("data-time-index")||"-1");return i>=0&&s>=0?{day:i,time:s}:null}updateSelectedCells(){if(!this.dragStartCell||!this.dragEndCell)return;this.selectedCells.clear();const e=Math.min(this.dragStartCell.day,this.dragEndCell.day),t=Math.max(this.dragStartCell.day,this.dragEndCell.day),i=Math.min(this.dragStartCell.time,this.dragEndCell.time),s=Math.max(this.dragStartCell.time,this.dragEndCell.time);for(let o=e;o<=t;o++)for(let e=i;e<=s;e++)this.selectedCells.add(`${o}-${e}`);this.requestUpdate()}getAverageValueFromSelection(){let e=0,t=0;return this.selectedCells.forEach(i=>{const[s,o]=i.split("-").map(Number),r=this.gridCells[s]?.[o];null!==r?.value&&(e+=r.value,t++)}),t>0?Math.round(e/t):Math.round((this.minValue+this.maxValue)/2)}handleValueChange(e){const t=e.target,i=parseFloat(t.value);isNaN(i)||(this.editingValue=Math.max(this.minValue,Math.min(this.maxValue,i)))}applyValueToSelection(){if(null===this.editingValue||0===this.selectedCells.size)return;const e=[];this.selectedCells.forEach(t=>{const[i,s]=t.split("-").map(Number),o=this.config.days[i],r=this.timeLabels[s];o&&r&&e.push({day:o,time:r,value:this.editingValue})}),this.dispatchEvent(new CustomEvent("schedule-changed",{detail:{mode:this.currentMode,changes:e},bubbles:!0,composed:!0})),this.closeValueEditor()}closeValueEditor(){this.showValueEditor=!1,this.editingValue=null,this.selectedCells.clear(),this.dragStartCell=null,this.dragEndCell=null,this.requestUpdate()}handleCellClick(e,t,i){if(!this.isDragging){const e=this.config.days[t],s=this.timeLabels[i],o=this.gridCells[t]?.[i]?.value;this.dispatchEvent(new CustomEvent("cell-clicked",{detail:{day:e,time:s,currentValue:o,dayIndex:t,timeIndex:i},bubbles:!0,composed:!0}))}}validateValue(e){return isNaN(e)?{isValid:!1,message:"Please enter a valid number"}:e<this.minValue?{isValid:!1,message:`Value must be at least ${this.minValue}°`}:e>this.maxValue?{isValid:!1,message:`Value must be at most ${this.maxValue}°`}:{isValid:!0}}handleKeyDown(e){"Escape"===e.key?this.closeValueEditor():"Enter"===e.key&&this.applyValueToSelection()}static get styles(){return n`
      :host {
        display: block;
        width: 100%;
      }

      .grid-container {
        display: flex;
        flex-direction: column;
        gap: 16px;
      }

      .grid-loading {
        display: flex;
        justify-content: center;
        align-items: center;
        min-height: 200px;
        color: var(--secondary-text-color);
      }

      .mode-selector {
        display: flex;
        gap: 8px;
        justify-content: center;
        flex-wrap: wrap;
      }

      .mode-button {
        padding: 8px 16px;
        border: 1px solid var(--divider-color);
        border-radius: 16px;
        background: var(--card-background-color);
        color: var(--primary-text-color);
        cursor: pointer;
        transition: all 0.2s ease;
      }

      .mode-button:hover {
        background: var(--secondary-background-color);
      }

      .mode-button.active {
        background: var(--primary-color);
        color: var(--text-primary-color);
        border-color: var(--primary-color);
      }

      .schedule-grid {
        display: flex;
        flex-direction: column;
        border: 1px solid var(--divider-color);
        border-radius: 8px;
        overflow: hidden;
        background: var(--card-background-color);
      }

      .time-header {
        display: grid;
        grid-template-columns: 100px repeat(auto-fit, minmax(40px, 1fr));
        background: var(--secondary-background-color);
        border-bottom: 1px solid var(--divider-color);
      }

      .time-label {
        padding: 8px 4px;
        text-align: center;
        font-size: 0.8em;
        color: var(--secondary-text-color);
        border-right: 1px solid var(--divider-color);
        writing-mode: vertical-rl;
        text-orientation: mixed;
      }

      .grid-row {
        display: grid;
        grid-template-columns: 100px repeat(auto-fit, minmax(40px, 1fr));
        border-bottom: 1px solid var(--divider-color);
      }

      .grid-row:last-child {
        border-bottom: none;
      }

      .day-label {
        padding: 12px 8px;
        background: var(--secondary-background-color);
        border-right: 1px solid var(--divider-color);
        font-weight: 500;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 0.9em;
      }

      .grid-cell {
        min-height: 40px;
        border-right: 1px solid var(--divider-color);
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 0.8em;
        font-weight: 500;
        color: white;
        text-shadow: 0 1px 2px rgba(0, 0, 0, 0.5);
        cursor: pointer;
        transition: all 0.2s ease;
        position: relative;
      }

      .grid-cell:hover {
        transform: scale(1.05);
        z-index: 1;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
      }

      .grid-cell:not(.active) {
        background: var(--card-background-color) !important;
        color: var(--secondary-text-color);
        text-shadow: none;
      }

      .grid-cell.current-time {
        box-shadow: inset 0 0 0 3px var(--accent-color);
        animation: pulse 2s infinite;
      }

      .grid-cell.selected {
        box-shadow: inset 0 0 0 2px var(--primary-color);
        transform: scale(1.02);
        z-index: 2;
      }

      .grid-cell.selected.current-time {
        box-shadow: inset 0 0 0 3px var(--accent-color), inset 0 0 0 2px var(--primary-color);
      }

      @keyframes pulse {
        0%, 100% { box-shadow: inset 0 0 0 3px var(--accent-color); }
        50% { box-shadow: inset 0 0 0 3px transparent; }
      }

      /* Value Editor Styles */
      .value-editor-overlay {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.5);
        z-index: 1000;
        display: flex;
        align-items: center;
        justify-content: center;
      }

      .value-editor {
        position: absolute;
        background: var(--card-background-color);
        border-radius: 8px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
        min-width: 280px;
        max-width: 90vw;
        transform: translate(-50%, -50%);
        border: 1px solid var(--divider-color);
      }

      .editor-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 16px;
        border-bottom: 1px solid var(--divider-color);
        font-weight: 500;
      }

      .close-btn {
        background: none;
        border: none;
        font-size: 20px;
        cursor: pointer;
        color: var(--secondary-text-color);
        padding: 0;
        width: 24px;
        height: 24px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 50%;
      }

      .close-btn:hover {
        background: var(--secondary-background-color);
        color: var(--primary-text-color);
      }

      .editor-content {
        padding: 16px;
      }

      .value-input-group {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 12px;
      }

      .value-input {
        flex: 1;
        padding: 8px 12px;
        border: 1px solid var(--divider-color);
        border-radius: 4px;
        background: var(--card-background-color);
        color: var(--primary-text-color);
        font-size: 16px;
      }

      .value-input:focus {
        outline: none;
        border-color: var(--primary-color);
        box-shadow: 0 0 0 2px rgba(var(--primary-color-rgb), 0.2);
      }

      .unit {
        color: var(--secondary-text-color);
        font-weight: 500;
      }

      .range-info, .selection-info {
        font-size: 0.9em;
        color: var(--secondary-text-color);
        margin-bottom: 8px;
      }

      .editor-actions {
        display: flex;
        gap: 8px;
        justify-content: flex-end;
        margin-top: 16px;
      }

      .cancel-btn, .apply-btn {
        padding: 8px 16px;
        border: 1px solid var(--divider-color);
        border-radius: 4px;
        cursor: pointer;
        font-size: 14px;
        transition: all 0.2s ease;
      }

      .cancel-btn {
        background: var(--card-background-color);
        color: var(--secondary-text-color);
      }

      .cancel-btn:hover {
        background: var(--secondary-background-color);
        color: var(--primary-text-color);
      }

      .apply-btn {
        background: var(--primary-color);
        color: var(--text-primary-color);
        border-color: var(--primary-color);
      }

      .apply-btn:hover:not(:disabled) {
        background: var(--primary-color);
        opacity: 0.9;
      }

      .apply-btn:disabled {
        opacity: 0.5;
        cursor: not-allowed;
      }

      .legend {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 8px 0;
        font-size: 0.9em;
        color: var(--secondary-text-color);
      }

      .legend-item {
        display: flex;
        align-items: center;
        gap: 8px;
      }

      .current-time-indicator {
        width: 16px;
        height: 16px;
        border: 3px solid var(--accent-color);
        border-radius: 2px;
      }

      .legend-gradient {
        display: flex;
        flex-direction: column;
        gap: 4px;
      }

      .gradient-bar {
        width: 100px;
        height: 16px;
        background: linear-gradient(to right, hsl(240, 70%, 50%), hsl(0, 70%, 50%));
        border-radius: 8px;
        border: 1px solid var(--divider-color);
      }

      .gradient-labels {
        display: flex;
        justify-content: space-between;
        font-size: 0.8em;
      }

      /* Responsive design */
      @media (max-width: 768px) {
        .time-header {
          grid-template-columns: 80px repeat(auto-fit, minmax(30px, 1fr));
        }

        .grid-row {
          grid-template-columns: 80px repeat(auto-fit, minmax(30px, 1fr));
        }

        .day-label {
          padding: 8px 4px;
          font-size: 0.8em;
        }

        .time-label {
          padding: 6px 2px;
          font-size: 0.7em;
        }

        .grid-cell {
          min-height: 32px;
          font-size: 0.7em;
        }

        .mode-selector {
          gap: 4px;
        }

        .mode-button {
          padding: 6px 12px;
          font-size: 0.9em;
        }
      }

      @media (max-width: 480px) {
        .time-header {
          grid-template-columns: 60px repeat(auto-fit, minmax(25px, 1fr));
        }

        .grid-row {
          grid-template-columns: 60px repeat(auto-fit, minmax(25px, 1fr));
        }

        .day-label {
          padding: 6px 2px;
          font-size: 0.7em;
        }

        .grid-cell {
          min-height: 28px;
          font-size: 0.6em;
        }

        .legend {
          flex-direction: column;
          gap: 8px;
          align-items: flex-start;
        }
      }
    `}};e([le({type:Object})],he.prototype,"scheduleData",void 0),e([le({type:String})],he.prototype,"currentMode",void 0),e([le({type:Object})],he.prototype,"config",void 0),e([le({type:Number})],he.prototype,"minValue",void 0),e([le({type:Number})],he.prototype,"maxValue",void 0),e([de()],he.prototype,"gridCells",void 0),e([de()],he.prototype,"timeLabels",void 0),e([de()],he.prototype,"currentTime",void 0),e([de()],he.prototype,"isDragging",void 0),e([de()],he.prototype,"dragStartCell",void 0),e([de()],he.prototype,"dragEndCell",void 0),e([de()],he.prototype,"selectedCells",void 0),e([de()],he.prototype,"editingValue",void 0),e([de()],he.prototype,"showValueEditor",void 0),e([de()],he.prototype,"editorPosition",void 0),he=e([ne("schedule-grid")],he);window.customCards=window.customCards||[],window.customCards.push({type:"roost-scheduler-card",name:"Roost Scheduler Card",description:"A card for managing climate schedules with presence-aware automation",preview:!0,documentationURL:"https://github.com/user/roost-scheduler"});let ue=class extends oe{constructor(){super(...arguments),this.scheduleData={},this.loading=!0,this.error=null,this.currentMode="home",this.gridConfig={resolution_minutes:30,start_hour:0,end_hour:24,days:["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]}}static async getConfigElement(){return await Promise.resolve().then(function(){return ge}),document.createElement("roost-scheduler-card-editor")}static getStubConfig(){return{type:"custom:roost-scheduler-card",entity:"",name:"Roost Scheduler",show_header:!0,resolution_minutes:30}}setConfig(e){if(!e)throw new Error("Invalid configuration");if(!e.entity)throw new Error("Entity is required");this.config={show_header:!0,resolution_minutes:30,...e}}getCardSize(){return 6}shouldUpdate(e){if(!this.config)return!1;if(e.has("config"))return!0;if(e.has("hass")){const t=e.get("hass");if(!t||t.states[this.config.entity]!==this.hass.states[this.config.entity])return!0}return!1}updated(e){super.updated(e),(e.has("config")||e.has("hass"))&&(this.updateGridConfig(),this.loadScheduleData())}updateGridConfig(){this.config&&(this.gridConfig={...this.gridConfig,resolution_minutes:this.config.resolution_minutes||30})}async loadScheduleData(){if(this.hass&&this.config.entity)try{this.loading=!0,this.error=null;const e=await this.hass.callWS({type:"roost_scheduler/get_schedule_grid",entity_id:this.config.entity});this.scheduleData=e.schedules||{}}catch(e){this.error=`Failed to load schedule data: ${e}`,console.error("Error loading schedule data:",e)}finally{this.loading=!1}}render(){if(!this.config||!this.hass)return O`
        <ha-card>
          <div class="card-content">
            <div class="error">Configuration required</div>
          </div>
        </ha-card>
      `;const e=this.hass.states[this.config.entity];return e?O`
      <ha-card>
        ${this.config.show_header?O`
              <div class="card-header">
                <div class="name">
                  ${this.config.name||e.attributes.friendly_name||this.config.entity}
                </div>
                <div class="version">v${"0.3.0"}</div>
              </div>
            `:""}
        
        <div class="card-content">
          ${this.loading?O`<div class="loading">Loading schedule data...</div>`:this.error?O`<div class="error">${this.error}</div>`:this.renderScheduleGrid()}
        </div>
      </ha-card>
    `:O`
        <ha-card>
          <div class="card-content">
            <div class="error">Entity "${this.config.entity}" not found</div>
          </div>
        </ha-card>
      `}renderScheduleGrid(){return Object.keys(this.scheduleData).length?O`
      <schedule-grid
        .scheduleData=${this.scheduleData}
        .currentMode=${this.currentMode}
        .config=${this.gridConfig}
        .minValue=${this.getEntityMinValue()}
        .maxValue=${this.getEntityMaxValue()}
        @mode-changed=${this.handleModeChanged}
        @schedule-changed=${this.handleScheduleChanged}
        @cell-clicked=${this.handleCellClicked}
      ></schedule-grid>
    `:O`
        <div class="no-data">
          <p>No schedule data available.</p>
          <p>Configure your schedule using the Roost Scheduler integration.</p>
        </div>
      `}getEntityMinValue(){const e=this.hass?.states[this.config.entity];return e?.attributes?.min_temp||10}getEntityMaxValue(){const e=this.hass?.states[this.config.entity];return e?.attributes?.max_temp||30}handleModeChanged(e){this.currentMode=e.detail.mode}async handleScheduleChanged(e){const{mode:t,changes:i}=e.detail;try{await this.hass.callWS({type:"roost_scheduler/update_schedule",entity_id:this.config.entity,mode:t,changes:i}),await this.loadScheduleData()}catch(e){console.error("Failed to update schedule:",e),this.error=`Failed to update schedule: ${e}`}}handleCellClicked(e){const{day:t,time:i,currentValue:s}=e.detail;console.log(`Cell clicked: ${t} ${i}, current value: ${s}`)}static get styles(){return n`
      :host {
        display: block;
      }

      ha-card {
        height: 100%;
        display: flex;
        flex-direction: column;
      }

      .card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 16px;
        border-bottom: 1px solid var(--divider-color);
      }

      .name {
        font-size: 1.2em;
        font-weight: 500;
        color: var(--primary-text-color);
      }

      .version {
        font-size: 0.8em;
        color: var(--secondary-text-color);
        opacity: 0.7;
      }

      .card-content {
        padding: 16px;
        flex: 1;
        display: flex;
        flex-direction: column;
      }

      .loading {
        display: flex;
        justify-content: center;
        align-items: center;
        min-height: 200px;
        color: var(--secondary-text-color);
      }

      .error {
        color: var(--error-color);
        text-align: center;
        padding: 20px;
        background: var(--error-color);
        background-opacity: 0.1;
        border-radius: 4px;
      }

      .no-data {
        text-align: center;
        color: var(--secondary-text-color);
        padding: 40px 20px;
      }

      .no-data p {
        margin: 8px 0;
      }

      .schedule-grid {
        flex: 1;
        min-height: 300px;
      }

      .grid-placeholder {
        text-align: center;
        color: var(--secondary-text-color);
        padding: 40px 20px;
        border: 2px dashed var(--divider-color);
        border-radius: 8px;
      }

      .grid-placeholder p {
        margin: 8px 0;
      }
    `}};e([le({attribute:!1})],ue.prototype,"hass",void 0),e([de()],ue.prototype,"config",void 0),e([de()],ue.prototype,"scheduleData",void 0),e([de()],ue.prototype,"loading",void 0),e([de()],ue.prototype,"error",void 0),e([de()],ue.prototype,"currentMode",void 0),e([de()],ue.prototype,"gridConfig",void 0),ue=e([ne("roost-scheduler-card")],ue);let pe=class extends oe{setConfig(e){this.config={...e}}render(){if(!this.hass||!this.config)return O``;const e=Object.keys(this.hass.states).filter(e=>e.startsWith("climate.")).map(e=>({value:e,label:this.hass.states[e].attributes.friendly_name||e}));return O`
      <div class="card-config">
        <div class="option">
          <label for="entity">Entity (Required)</label>
          <select
            id="entity"
            .value=${this.config.entity||""}
            @change=${this.handleEntityChange}
          >
            <option value="">Select a climate entity...</option>
            ${e.map(e=>O`
                <option value=${e.value} ?selected=${e.value===this.config.entity}>
                  ${e.label}
                </option>
              `)}
          </select>
        </div>

        <div class="option">
          <label for="name">Name (Optional)</label>
          <input
            type="text"
            id="name"
            .value=${this.config.name||""}
            @input=${this.handleNameChange}
            placeholder="Card title"
          />
        </div>

        <div class="option">
          <label>
            <input
              type="checkbox"
              .checked=${!1!==this.config.show_header}
              @change=${this.handleShowHeaderChange}
            />
            Show header
          </label>
        </div>

        <div class="option">
          <label for="resolution">Time Resolution</label>
          <select
            id="resolution"
            .value=${this.config.resolution_minutes||30}
            @change=${this.handleResolutionChange}
          >
            <option value="15">15 minutes</option>
            <option value="30">30 minutes</option>
            <option value="60">60 minutes</option>
          </select>
        </div>
      </div>
    `}handleEntityChange(e){const t=e.target;this.config.entity!==t.value&&(this.config={...this.config,entity:t.value},this.dispatchConfigChanged())}handleNameChange(e){const t=e.target;this.config.name!==t.value&&(this.config={...this.config,name:t.value},this.dispatchConfigChanged())}handleShowHeaderChange(e){const t=e.target;this.config.show_header!==t.checked&&(this.config={...this.config,show_header:t.checked},this.dispatchConfigChanged())}handleResolutionChange(e){const t=e.target,i=parseInt(t.value);this.config.resolution_minutes!==i&&(this.config={...this.config,resolution_minutes:i},this.dispatchConfigChanged())}dispatchConfigChanged(){const e=new CustomEvent("config-changed",{detail:{config:this.config},bubbles:!0,composed:!0});this.dispatchEvent(e)}static get styles(){return n`
      .card-config {
        display: flex;
        flex-direction: column;
        gap: 16px;
      }

      .option {
        display: flex;
        flex-direction: column;
        gap: 4px;
      }

      .option label {
        font-weight: 500;
        color: var(--primary-text-color);
      }

      .option input,
      .option select {
        padding: 8px;
        border: 1px solid var(--divider-color);
        border-radius: 4px;
        background: var(--card-background-color);
        color: var(--primary-text-color);
        font-size: 14px;
      }

      .option input[type="checkbox"] {
        width: auto;
        margin-right: 8px;
      }

      .option label:has(input[type="checkbox"]) {
        flex-direction: row;
        align-items: center;
      }
    `}};e([le({attribute:!1})],pe.prototype,"hass",void 0),e([de()],pe.prototype,"config",void 0),pe=e([ne("roost-scheduler-card-editor")],pe);var ge=Object.freeze({__proto__:null,get RoostSchedulerCardEditor(){return pe}});export{ue as RoostSchedulerCard};
