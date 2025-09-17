function t(t,e,i,s){var r,o=arguments.length,n=o<3?e:null===s?s=Object.getOwnPropertyDescriptor(e,i):s;if("object"==typeof Reflect&&"function"==typeof Reflect.decorate)n=Reflect.decorate(t,e,i,s);else for(var a=t.length-1;a>=0;a--)(r=t[a])&&(n=(o<3?r(n):o>3?r(e,i,n):r(e,i))||n);return o>3&&n&&Object.defineProperty(e,i,n),n}"function"==typeof SuppressedError&&SuppressedError;
/**
 * @license
 * Copyright 2019 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */
const e=window,i=e.ShadowRoot&&(void 0===e.ShadyCSS||e.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,s=Symbol(),r=new WeakMap;let o=class{constructor(t,e,i){if(this._$cssResult$=!0,i!==s)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=t,this.t=e}get styleSheet(){let t=this.o;const e=this.t;if(i&&void 0===t){const i=void 0!==e&&1===e.length;i&&(t=r.get(e)),void 0===t&&((this.o=t=new CSSStyleSheet).replaceSync(this.cssText),i&&r.set(e,t))}return t}toString(){return this.cssText}};const n=(t,...e)=>{const i=1===t.length?t[0]:e.reduce((e,i,s)=>e+(t=>{if(!0===t._$cssResult$)return t.cssText;if("number"==typeof t)return t;throw Error("Value passed to 'css' function must be a 'css' function result: "+t+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(i)+t[s+1],t[0]);return new o(i,t,s)},a=i?t=>t:t=>t instanceof CSSStyleSheet?(t=>{let e="";for(const i of t.cssRules)e+=i.cssText;return(t=>new o("string"==typeof t?t:t+"",void 0,s))(e)})(t):t;
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */var l;const d=window,c=d.trustedTypes,h=c?c.emptyScript:"",u=d.reactiveElementPolyfillSupport,p={toAttribute(t,e){switch(e){case Boolean:t=t?h:null;break;case Object:case Array:t=null==t?t:JSON.stringify(t)}return t},fromAttribute(t,e){let i=t;switch(e){case Boolean:i=null!==t;break;case Number:i=null===t?null:Number(t);break;case Object:case Array:try{i=JSON.parse(t)}catch(t){i=null}}return i}},g=(t,e)=>e!==t&&(e==e||t==t),v={attribute:!0,type:String,converter:p,reflect:!1,hasChanged:g},m="finalized";let f=class extends HTMLElement{constructor(){super(),this._$Ei=new Map,this.isUpdatePending=!1,this.hasUpdated=!1,this._$El=null,this._$Eu()}static addInitializer(t){var e;this.finalize(),(null!==(e=this.h)&&void 0!==e?e:this.h=[]).push(t)}static get observedAttributes(){this.finalize();const t=[];return this.elementProperties.forEach((e,i)=>{const s=this._$Ep(i,e);void 0!==s&&(this._$Ev.set(s,i),t.push(s))}),t}static createProperty(t,e=v){if(e.state&&(e.attribute=!1),this.finalize(),this.elementProperties.set(t,e),!e.noAccessor&&!this.prototype.hasOwnProperty(t)){const i="symbol"==typeof t?Symbol():"__"+t,s=this.getPropertyDescriptor(t,i,e);void 0!==s&&Object.defineProperty(this.prototype,t,s)}}static getPropertyDescriptor(t,e,i){return{get(){return this[e]},set(s){const r=this[t];this[e]=s,this.requestUpdate(t,r,i)},configurable:!0,enumerable:!0}}static getPropertyOptions(t){return this.elementProperties.get(t)||v}static finalize(){if(this.hasOwnProperty(m))return!1;this[m]=!0;const t=Object.getPrototypeOf(this);if(t.finalize(),void 0!==t.h&&(this.h=[...t.h]),this.elementProperties=new Map(t.elementProperties),this._$Ev=new Map,this.hasOwnProperty("properties")){const t=this.properties,e=[...Object.getOwnPropertyNames(t),...Object.getOwnPropertySymbols(t)];for(const i of e)this.createProperty(i,t[i])}return this.elementStyles=this.finalizeStyles(this.styles),!0}static finalizeStyles(t){const e=[];if(Array.isArray(t)){const i=new Set(t.flat(1/0).reverse());for(const t of i)e.unshift(a(t))}else void 0!==t&&e.push(a(t));return e}static _$Ep(t,e){const i=e.attribute;return!1===i?void 0:"string"==typeof i?i:"string"==typeof t?t.toLowerCase():void 0}_$Eu(){var t;this._$E_=new Promise(t=>this.enableUpdating=t),this._$AL=new Map,this._$Eg(),this.requestUpdate(),null===(t=this.constructor.h)||void 0===t||t.forEach(t=>t(this))}addController(t){var e,i;(null!==(e=this._$ES)&&void 0!==e?e:this._$ES=[]).push(t),void 0!==this.renderRoot&&this.isConnected&&(null===(i=t.hostConnected)||void 0===i||i.call(t))}removeController(t){var e;null===(e=this._$ES)||void 0===e||e.splice(this._$ES.indexOf(t)>>>0,1)}_$Eg(){this.constructor.elementProperties.forEach((t,e)=>{this.hasOwnProperty(e)&&(this._$Ei.set(e,this[e]),delete this[e])})}createRenderRoot(){var t;const s=null!==(t=this.shadowRoot)&&void 0!==t?t:this.attachShadow(this.constructor.shadowRootOptions);return((t,s)=>{i?t.adoptedStyleSheets=s.map(t=>t instanceof CSSStyleSheet?t:t.styleSheet):s.forEach(i=>{const s=document.createElement("style"),r=e.litNonce;void 0!==r&&s.setAttribute("nonce",r),s.textContent=i.cssText,t.appendChild(s)})})(s,this.constructor.elementStyles),s}connectedCallback(){var t;void 0===this.renderRoot&&(this.renderRoot=this.createRenderRoot()),this.enableUpdating(!0),null===(t=this._$ES)||void 0===t||t.forEach(t=>{var e;return null===(e=t.hostConnected)||void 0===e?void 0:e.call(t)})}enableUpdating(t){}disconnectedCallback(){var t;null===(t=this._$ES)||void 0===t||t.forEach(t=>{var e;return null===(e=t.hostDisconnected)||void 0===e?void 0:e.call(t)})}attributeChangedCallback(t,e,i){this._$AK(t,i)}_$EO(t,e,i=v){var s;const r=this.constructor._$Ep(t,i);if(void 0!==r&&!0===i.reflect){const o=(void 0!==(null===(s=i.converter)||void 0===s?void 0:s.toAttribute)?i.converter:p).toAttribute(e,i.type);this._$El=t,null==o?this.removeAttribute(r):this.setAttribute(r,o),this._$El=null}}_$AK(t,e){var i;const s=this.constructor,r=s._$Ev.get(t);if(void 0!==r&&this._$El!==r){const t=s.getPropertyOptions(r),o="function"==typeof t.converter?{fromAttribute:t.converter}:void 0!==(null===(i=t.converter)||void 0===i?void 0:i.fromAttribute)?t.converter:p;this._$El=r,this[r]=o.fromAttribute(e,t.type),this._$El=null}}requestUpdate(t,e,i){let s=!0;void 0!==t&&(((i=i||this.constructor.getPropertyOptions(t)).hasChanged||g)(this[t],e)?(this._$AL.has(t)||this._$AL.set(t,e),!0===i.reflect&&this._$El!==t&&(void 0===this._$EC&&(this._$EC=new Map),this._$EC.set(t,i))):s=!1),!this.isUpdatePending&&s&&(this._$E_=this._$Ej())}async _$Ej(){this.isUpdatePending=!0;try{await this._$E_}catch(t){Promise.reject(t)}const t=this.scheduleUpdate();return null!=t&&await t,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){var t;if(!this.isUpdatePending)return;this.hasUpdated,this._$Ei&&(this._$Ei.forEach((t,e)=>this[e]=t),this._$Ei=void 0);let e=!1;const i=this._$AL;try{e=this.shouldUpdate(i),e?(this.willUpdate(i),null===(t=this._$ES)||void 0===t||t.forEach(t=>{var e;return null===(e=t.hostUpdate)||void 0===e?void 0:e.call(t)}),this.update(i)):this._$Ek()}catch(t){throw e=!1,this._$Ek(),t}e&&this._$AE(i)}willUpdate(t){}_$AE(t){var e;null===(e=this._$ES)||void 0===e||e.forEach(t=>{var e;return null===(e=t.hostUpdated)||void 0===e?void 0:e.call(t)}),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(t)),this.updated(t)}_$Ek(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$E_}shouldUpdate(t){return!0}update(t){void 0!==this._$EC&&(this._$EC.forEach((t,e)=>this._$EO(e,this[e],t)),this._$EC=void 0),this._$Ek()}updated(t){}firstUpdated(t){}};
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */
var y;f[m]=!0,f.elementProperties=new Map,f.elementStyles=[],f.shadowRootOptions={mode:"open"},null==u||u({ReactiveElement:f}),(null!==(l=d.reactiveElementVersions)&&void 0!==l?l:d.reactiveElementVersions=[]).push("1.6.3");const $=window,_=$.trustedTypes,x=_?_.createPolicy("lit-html",{createHTML:t=>t}):void 0,b="$lit$",A=`lit$${(Math.random()+"").slice(9)}$`,w="?"+A,C=`<${w}>`,E=document,S=()=>E.createComment(""),k=t=>null===t||"object"!=typeof t&&"function"!=typeof t,M=Array.isArray,T="[ \t\n\f\r]",U=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,P=/-->/g,N=/>/g,O=RegExp(`>|${T}(?:([^\\s"'>=/]+)(${T}*=${T}*(?:[^ \t\n\f\r"'\`<>=]|("|')|))|$)`,"g"),R=/'/g,H=/"/g,j=/^(?:script|style|textarea|title)$/i,z=(t=>(e,...i)=>({_$litType$:t,strings:e,values:i}))(1),D=Symbol.for("lit-noChange"),V=Symbol.for("lit-nothing"),L=new WeakMap,I=E.createTreeWalker(E,129,null,!1);function B(t,e){if(!Array.isArray(t)||!t.hasOwnProperty("raw"))throw Error("invalid template strings array");return void 0!==x?x.createHTML(e):e}const G=(t,e)=>{const i=t.length-1,s=[];let r,o=2===e?"<svg>":"",n=U;for(let e=0;e<i;e++){const i=t[e];let a,l,d=-1,c=0;for(;c<i.length&&(n.lastIndex=c,l=n.exec(i),null!==l);)c=n.lastIndex,n===U?"!--"===l[1]?n=P:void 0!==l[1]?n=N:void 0!==l[2]?(j.test(l[2])&&(r=RegExp("</"+l[2],"g")),n=O):void 0!==l[3]&&(n=O):n===O?">"===l[0]?(n=null!=r?r:U,d=-1):void 0===l[1]?d=-2:(d=n.lastIndex-l[2].length,a=l[1],n=void 0===l[3]?O:'"'===l[3]?H:R):n===H||n===R?n=O:n===P||n===N?n=U:(n=O,r=void 0);const h=n===O&&t[e+1].startsWith("/>")?" ":"";o+=n===U?i+C:d>=0?(s.push(a),i.slice(0,d)+b+i.slice(d)+A+h):i+A+(-2===d?(s.push(void 0),e):h)}return[B(t,o+(t[i]||"<?>")+(2===e?"</svg>":"")),s]};class W{constructor({strings:t,_$litType$:e},i){let s;this.parts=[];let r=0,o=0;const n=t.length-1,a=this.parts,[l,d]=G(t,e);if(this.el=W.createElement(l,i),I.currentNode=this.el.content,2===e){const t=this.el.content,e=t.firstChild;e.remove(),t.append(...e.childNodes)}for(;null!==(s=I.nextNode())&&a.length<n;){if(1===s.nodeType){if(s.hasAttributes()){const t=[];for(const e of s.getAttributeNames())if(e.endsWith(b)||e.startsWith(A)){const i=d[o++];if(t.push(e),void 0!==i){const t=s.getAttribute(i.toLowerCase()+b).split(A),e=/([.?@])?(.*)/.exec(i);a.push({type:1,index:r,name:e[2],strings:t,ctor:"."===e[1]?Z:"?"===e[1]?X:"@"===e[1]?Y:J})}else a.push({type:6,index:r})}for(const e of t)s.removeAttribute(e)}if(j.test(s.tagName)){const t=s.textContent.split(A),e=t.length-1;if(e>0){s.textContent=_?_.emptyScript:"";for(let i=0;i<e;i++)s.append(t[i],S()),I.nextNode(),a.push({type:2,index:++r});s.append(t[e],S())}}}else if(8===s.nodeType)if(s.data===w)a.push({type:2,index:r});else{let t=-1;for(;-1!==(t=s.data.indexOf(A,t+1));)a.push({type:7,index:r}),t+=A.length-1}r++}}static createElement(t,e){const i=E.createElement("template");return i.innerHTML=t,i}}function q(t,e,i=t,s){var r,o,n,a;if(e===D)return e;let l=void 0!==s?null===(r=i._$Co)||void 0===r?void 0:r[s]:i._$Cl;const d=k(e)?void 0:e._$litDirective$;return(null==l?void 0:l.constructor)!==d&&(null===(o=null==l?void 0:l._$AO)||void 0===o||o.call(l,!1),void 0===d?l=void 0:(l=new d(t),l._$AT(t,i,s)),void 0!==s?(null!==(n=(a=i)._$Co)&&void 0!==n?n:a._$Co=[])[s]=l:i._$Cl=l),void 0!==l&&(e=q(t,l._$AS(t,e.values),l,s)),e}class F{constructor(t,e){this._$AV=[],this._$AN=void 0,this._$AD=t,this._$AM=e}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(t){var e;const{el:{content:i},parts:s}=this._$AD,r=(null!==(e=null==t?void 0:t.creationScope)&&void 0!==e?e:E).importNode(i,!0);I.currentNode=r;let o=I.nextNode(),n=0,a=0,l=s[0];for(;void 0!==l;){if(n===l.index){let e;2===l.type?e=new K(o,o.nextSibling,this,t):1===l.type?e=new l.ctor(o,l.name,l.strings,this,t):6===l.type&&(e=new tt(o,this,t)),this._$AV.push(e),l=s[++a]}n!==(null==l?void 0:l.index)&&(o=I.nextNode(),n++)}return I.currentNode=E,r}v(t){let e=0;for(const i of this._$AV)void 0!==i&&(void 0!==i.strings?(i._$AI(t,i,e),e+=i.strings.length-2):i._$AI(t[e])),e++}}class K{constructor(t,e,i,s){var r;this.type=2,this._$AH=V,this._$AN=void 0,this._$AA=t,this._$AB=e,this._$AM=i,this.options=s,this._$Cp=null===(r=null==s?void 0:s.isConnected)||void 0===r||r}get _$AU(){var t,e;return null!==(e=null===(t=this._$AM)||void 0===t?void 0:t._$AU)&&void 0!==e?e:this._$Cp}get parentNode(){let t=this._$AA.parentNode;const e=this._$AM;return void 0!==e&&11===(null==t?void 0:t.nodeType)&&(t=e.parentNode),t}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(t,e=this){t=q(this,t,e),k(t)?t===V||null==t||""===t?(this._$AH!==V&&this._$AR(),this._$AH=V):t!==this._$AH&&t!==D&&this._(t):void 0!==t._$litType$?this.g(t):void 0!==t.nodeType?this.$(t):(t=>M(t)||"function"==typeof(null==t?void 0:t[Symbol.iterator]))(t)?this.T(t):this._(t)}k(t){return this._$AA.parentNode.insertBefore(t,this._$AB)}$(t){this._$AH!==t&&(this._$AR(),this._$AH=this.k(t))}_(t){this._$AH!==V&&k(this._$AH)?this._$AA.nextSibling.data=t:this.$(E.createTextNode(t)),this._$AH=t}g(t){var e;const{values:i,_$litType$:s}=t,r="number"==typeof s?this._$AC(t):(void 0===s.el&&(s.el=W.createElement(B(s.h,s.h[0]),this.options)),s);if((null===(e=this._$AH)||void 0===e?void 0:e._$AD)===r)this._$AH.v(i);else{const t=new F(r,this),e=t.u(this.options);t.v(i),this.$(e),this._$AH=t}}_$AC(t){let e=L.get(t.strings);return void 0===e&&L.set(t.strings,e=new W(t)),e}T(t){M(this._$AH)||(this._$AH=[],this._$AR());const e=this._$AH;let i,s=0;for(const r of t)s===e.length?e.push(i=new K(this.k(S()),this.k(S()),this,this.options)):i=e[s],i._$AI(r),s++;s<e.length&&(this._$AR(i&&i._$AB.nextSibling,s),e.length=s)}_$AR(t=this._$AA.nextSibling,e){var i;for(null===(i=this._$AP)||void 0===i||i.call(this,!1,!0,e);t&&t!==this._$AB;){const e=t.nextSibling;t.remove(),t=e}}setConnected(t){var e;void 0===this._$AM&&(this._$Cp=t,null===(e=this._$AP)||void 0===e||e.call(this,t))}}class J{constructor(t,e,i,s,r){this.type=1,this._$AH=V,this._$AN=void 0,this.element=t,this.name=e,this._$AM=s,this.options=r,i.length>2||""!==i[0]||""!==i[1]?(this._$AH=Array(i.length-1).fill(new String),this.strings=i):this._$AH=V}get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}_$AI(t,e=this,i,s){const r=this.strings;let o=!1;if(void 0===r)t=q(this,t,e,0),o=!k(t)||t!==this._$AH&&t!==D,o&&(this._$AH=t);else{const s=t;let n,a;for(t=r[0],n=0;n<r.length-1;n++)a=q(this,s[i+n],e,n),a===D&&(a=this._$AH[n]),o||(o=!k(a)||a!==this._$AH[n]),a===V?t=V:t!==V&&(t+=(null!=a?a:"")+r[n+1]),this._$AH[n]=a}o&&!s&&this.j(t)}j(t){t===V?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,null!=t?t:"")}}class Z extends J{constructor(){super(...arguments),this.type=3}j(t){this.element[this.name]=t===V?void 0:t}}const Q=_?_.emptyScript:"";class X extends J{constructor(){super(...arguments),this.type=4}j(t){t&&t!==V?this.element.setAttribute(this.name,Q):this.element.removeAttribute(this.name)}}class Y extends J{constructor(t,e,i,s,r){super(t,e,i,s,r),this.type=5}_$AI(t,e=this){var i;if((t=null!==(i=q(this,t,e,0))&&void 0!==i?i:V)===D)return;const s=this._$AH,r=t===V&&s!==V||t.capture!==s.capture||t.once!==s.once||t.passive!==s.passive,o=t!==V&&(s===V||r);r&&this.element.removeEventListener(this.name,this,s),o&&this.element.addEventListener(this.name,this,t),this._$AH=t}handleEvent(t){var e,i;"function"==typeof this._$AH?this._$AH.call(null!==(i=null===(e=this.options)||void 0===e?void 0:e.host)&&void 0!==i?i:this.element,t):this._$AH.handleEvent(t)}}class tt{constructor(t,e,i){this.element=t,this.type=6,this._$AN=void 0,this._$AM=e,this.options=i}get _$AU(){return this._$AM._$AU}_$AI(t){q(this,t)}}const et=$.litHtmlPolyfillSupport;null==et||et(W,K),(null!==(y=$.litHtmlVersions)&&void 0!==y?y:$.litHtmlVersions=[]).push("2.8.0");
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */
var it,st;class rt extends f{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){var t,e;const i=super.createRenderRoot();return null!==(t=(e=this.renderOptions).renderBefore)&&void 0!==t||(e.renderBefore=i.firstChild),i}update(t){const e=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(t),this._$Do=((t,e,i)=>{var s,r;const o=null!==(s=null==i?void 0:i.renderBefore)&&void 0!==s?s:e;let n=o._$litPart$;if(void 0===n){const t=null!==(r=null==i?void 0:i.renderBefore)&&void 0!==r?r:null;o._$litPart$=n=new K(e.insertBefore(S(),t),t,void 0,null!=i?i:{})}return n._$AI(t),n})(e,this.renderRoot,this.renderOptions)}connectedCallback(){var t;super.connectedCallback(),null===(t=this._$Do)||void 0===t||t.setConnected(!0)}disconnectedCallback(){var t;super.disconnectedCallback(),null===(t=this._$Do)||void 0===t||t.setConnected(!1)}render(){return D}}rt.finalized=!0,rt._$litElement$=!0,null===(it=globalThis.litElementHydrateSupport)||void 0===it||it.call(globalThis,{LitElement:rt});const ot=globalThis.litElementPolyfillSupport;null==ot||ot({LitElement:rt}),(null!==(st=globalThis.litElementVersions)&&void 0!==st?st:globalThis.litElementVersions=[]).push("3.3.3");
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */
const nt=t=>e=>"function"==typeof e?((t,e)=>(customElements.define(t,e),e))(t,e):((t,e)=>{const{kind:i,elements:s}=e;return{kind:i,elements:s,finisher(e){customElements.define(t,e)}}})(t,e),at=(t,e)=>"method"===e.kind&&e.descriptor&&!("value"in e.descriptor)?{...e,finisher(i){i.createProperty(e.key,t)}}:{kind:"field",key:Symbol(),placement:"own",descriptor:{},originalKey:e.key,initializer(){"function"==typeof e.initializer&&(this[e.key]=e.initializer.call(this))},finisher(i){i.createProperty(e.key,t)}};
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */function lt(t){return(e,i)=>void 0!==i?((t,e,i)=>{e.constructor.createProperty(i,t)})(t,e,i):at(t,e)}
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */function dt(t){return lt({...t,state:!0})}
/**
 * @license
 * Copyright 2021 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */var ct;null===(ct=window.HTMLSlotElement)||void 0===ct||ct.prototype.assignedElements;let ht=class extends rt{constructor(){super(...arguments),this.scheduleData={},this.currentMode="home",this.config={resolution_minutes:30,start_hour:0,end_hour:24,days:["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]},this.minValue=10,this.maxValue=30,this.gridCells=[],this.timeLabels=[],this.currentTime=new Date}connectedCallback(){super.connectedCallback(),this.updateCurrentTime(),setInterval(()=>this.updateCurrentTime(),6e4)}willUpdate(t){(t.has("scheduleData")||t.has("config")||t.has("currentMode"))&&this.generateGrid()}updateCurrentTime(){this.currentTime=new Date,this.requestUpdate()}generateGrid(){const{resolution_minutes:t,start_hour:e,end_hour:i,days:s}=this.config;this.timeLabels=[];const r=60*(i-e);for(let i=0;i<r;i+=t){const t=Math.floor(i/60)+e,s=i%60;this.timeLabels.push(`${t.toString().padStart(2,"0")}:${s.toString().padStart(2,"0")}`)}this.gridCells=s.map(t=>this.timeLabels.map(e=>{const i=this.getValueForSlot(t,e),s=this.isCurrentTimeSlot(t,e);return{day:t,time:e,value:i,isActive:null!==i,isCurrentTime:s}}))}getValueForSlot(t,e){const i=this.scheduleData[this.currentMode];if(!i||!i[t])return null;const s=i[t],r=this.timeToMinutes(e);for(const t of s){const e=this.timeToMinutes(t.start_time),i=this.timeToMinutes(t.end_time);if(r>=e&&r<i)return t.target_value}return null}isCurrentTimeSlot(t,e){const i=this.currentTime,s=this.getDayName(i.getDay()),r=60*i.getHours()+i.getMinutes(),o=this.timeToMinutes(e),n=o+this.config.resolution_minutes;return t===s&&r>=o&&r<n}timeToMinutes(t){const[e,i]=t.split(":").map(Number);return 60*e+i}getDayName(t){return["sunday","monday","tuesday","wednesday","thursday","friday","saturday"][t]}getValueColor(t){if(null===t)return"transparent";const e=(t-this.minValue)/(this.maxValue-this.minValue);return`hsl(${240*(1-Math.max(0,Math.min(1,e)))}, 70%, 50%)`}formatValue(t){return null===t?"":`${t}°`}render(){return this.gridCells.length&&Object.keys(this.scheduleData).length?z`
      <div class="grid-container">
        <!-- Mode selector -->
        <div class="mode-selector">
          ${Object.keys(this.scheduleData).map(t=>z`
            <button 
              class="mode-button ${t===this.currentMode?"active":""}"
              @click=${()=>this.selectMode(t)}
            >
              ${t.charAt(0).toUpperCase()+t.slice(1)}
            </button>
          `)}
        </div>

        <!-- Grid -->
        <div class="schedule-grid">
          <!-- Time header -->
          <div class="time-header">
            <div class="day-label"></div>
            ${this.timeLabels.map(t=>z`
              <div class="time-label">${t}</div>
            `)}
          </div>

          <!-- Grid rows -->
          ${this.config.days.map((t,e)=>z`
            <div class="grid-row">
              <div class="day-label">${t.charAt(0).toUpperCase()+t.slice(1)}</div>
              ${this.gridCells[e]?.map(t=>z`
                <div 
                  class="grid-cell ${t.isActive?"active":""} ${t.isCurrentTime?"current-time":""}"
                  style="background-color: ${this.getValueColor(t.value)}"
                  title="${t.day} ${t.time}${t.value?` - ${this.formatValue(t.value)}`:""}"
                >
                  ${t.isActive?this.formatValue(t.value):""}
                </div>
              `)||[]}
            </div>
          `)}
        </div>

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
    `:z`
        <div class="grid-loading">
          <p>Generating schedule grid...</p>
        </div>
      `}selectMode(t){this.currentMode=t,this.dispatchEvent(new CustomEvent("mode-changed",{detail:{mode:t},bubbles:!0,composed:!0}))}static get styles(){return n`
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

      @keyframes pulse {
        0%, 100% { box-shadow: inset 0 0 0 3px var(--accent-color); }
        50% { box-shadow: inset 0 0 0 3px transparent; }
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
    `}};t([lt({type:Object})],ht.prototype,"scheduleData",void 0),t([lt({type:String})],ht.prototype,"currentMode",void 0),t([lt({type:Object})],ht.prototype,"config",void 0),t([lt({type:Number})],ht.prototype,"minValue",void 0),t([lt({type:Number})],ht.prototype,"maxValue",void 0),t([dt()],ht.prototype,"gridCells",void 0),t([dt()],ht.prototype,"timeLabels",void 0),t([dt()],ht.prototype,"currentTime",void 0),ht=t([nt("schedule-grid")],ht);window.customCards=window.customCards||[],window.customCards.push({type:"roost-scheduler-card",name:"Roost Scheduler Card",description:"A card for managing climate schedules with presence-aware automation",preview:!0,documentationURL:"https://github.com/user/roost-scheduler"});let ut=class extends rt{constructor(){super(...arguments),this.scheduleData={},this.loading=!0,this.error=null,this.currentMode="home",this.gridConfig={resolution_minutes:30,start_hour:0,end_hour:24,days:["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]}}static async getConfigElement(){return await Promise.resolve().then(function(){return gt}),document.createElement("roost-scheduler-card-editor")}static getStubConfig(){return{type:"custom:roost-scheduler-card",entity:"",name:"Roost Scheduler",show_header:!0,resolution_minutes:30}}setConfig(t){if(!t)throw new Error("Invalid configuration");if(!t.entity)throw new Error("Entity is required");this.config={show_header:!0,resolution_minutes:30,...t}}getCardSize(){return 6}shouldUpdate(t){if(!this.config)return!1;if(t.has("config"))return!0;if(t.has("hass")){const e=t.get("hass");if(!e||e.states[this.config.entity]!==this.hass.states[this.config.entity])return!0}return!1}updated(t){super.updated(t),(t.has("config")||t.has("hass"))&&(this.updateGridConfig(),this.loadScheduleData())}updateGridConfig(){this.config&&(this.gridConfig={...this.gridConfig,resolution_minutes:this.config.resolution_minutes||30})}async loadScheduleData(){if(this.hass&&this.config.entity)try{this.loading=!0,this.error=null;const t=await this.hass.callWS({type:"roost_scheduler/get_schedule_grid",entity_id:this.config.entity});this.scheduleData=t.schedules||{}}catch(t){this.error=`Failed to load schedule data: ${t}`,console.error("Error loading schedule data:",t)}finally{this.loading=!1}}render(){if(!this.config||!this.hass)return z`
        <ha-card>
          <div class="card-content">
            <div class="error">Configuration required</div>
          </div>
        </ha-card>
      `;const t=this.hass.states[this.config.entity];return t?z`
      <ha-card>
        ${this.config.show_header?z`
              <div class="card-header">
                <div class="name">
                  ${this.config.name||t.attributes.friendly_name||this.config.entity}
                </div>
                <div class="version">v${"0.3.0"}</div>
              </div>
            `:""}
        
        <div class="card-content">
          ${this.loading?z`<div class="loading">Loading schedule data...</div>`:this.error?z`<div class="error">${this.error}</div>`:this.renderScheduleGrid()}
        </div>
      </ha-card>
    `:z`
        <ha-card>
          <div class="card-content">
            <div class="error">Entity "${this.config.entity}" not found</div>
          </div>
        </ha-card>
      `}renderScheduleGrid(){return Object.keys(this.scheduleData).length?z`
      <schedule-grid
        .scheduleData=${this.scheduleData}
        .currentMode=${this.currentMode}
        .config=${this.gridConfig}
        .minValue=${this.getEntityMinValue()}
        .maxValue=${this.getEntityMaxValue()}
        @mode-changed=${this.handleModeChanged}
      ></schedule-grid>
    `:z`
        <div class="no-data">
          <p>No schedule data available.</p>
          <p>Configure your schedule using the Roost Scheduler integration.</p>
        </div>
      `}getEntityMinValue(){const t=this.hass?.states[this.config.entity];return t?.attributes?.min_temp||10}getEntityMaxValue(){const t=this.hass?.states[this.config.entity];return t?.attributes?.max_temp||30}handleModeChanged(t){this.currentMode=t.detail.mode}static get styles(){return n`
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
    `}};t([lt({attribute:!1})],ut.prototype,"hass",void 0),t([dt()],ut.prototype,"config",void 0),t([dt()],ut.prototype,"scheduleData",void 0),t([dt()],ut.prototype,"loading",void 0),t([dt()],ut.prototype,"error",void 0),t([dt()],ut.prototype,"currentMode",void 0),t([dt()],ut.prototype,"gridConfig",void 0),ut=t([nt("roost-scheduler-card")],ut);let pt=class extends rt{setConfig(t){this.config={...t}}render(){if(!this.hass||!this.config)return z``;const t=Object.keys(this.hass.states).filter(t=>t.startsWith("climate.")).map(t=>({value:t,label:this.hass.states[t].attributes.friendly_name||t}));return z`
      <div class="card-config">
        <div class="option">
          <label for="entity">Entity (Required)</label>
          <select
            id="entity"
            .value=${this.config.entity||""}
            @change=${this.handleEntityChange}
          >
            <option value="">Select a climate entity...</option>
            ${t.map(t=>z`
                <option value=${t.value} ?selected=${t.value===this.config.entity}>
                  ${t.label}
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
    `}handleEntityChange(t){const e=t.target;this.config.entity!==e.value&&(this.config={...this.config,entity:e.value},this.dispatchConfigChanged())}handleNameChange(t){const e=t.target;this.config.name!==e.value&&(this.config={...this.config,name:e.value},this.dispatchConfigChanged())}handleShowHeaderChange(t){const e=t.target;this.config.show_header!==e.checked&&(this.config={...this.config,show_header:e.checked},this.dispatchConfigChanged())}handleResolutionChange(t){const e=t.target,i=parseInt(e.value);this.config.resolution_minutes!==i&&(this.config={...this.config,resolution_minutes:i},this.dispatchConfigChanged())}dispatchConfigChanged(){const t=new CustomEvent("config-changed",{detail:{config:this.config},bubbles:!0,composed:!0});this.dispatchEvent(t)}static get styles(){return n`
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
    `}};t([lt({attribute:!1})],pt.prototype,"hass",void 0),t([dt()],pt.prototype,"config",void 0),pt=t([nt("roost-scheduler-card-editor")],pt);var gt=Object.freeze({__proto__:null,get RoostSchedulerCardEditor(){return pt}});export{ut as RoostSchedulerCard};
