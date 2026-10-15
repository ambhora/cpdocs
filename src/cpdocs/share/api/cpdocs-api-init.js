// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 cpdocs developers
document.documentElement.classList.add("js");try{for(const k of ["sidebar","toc"]){const v=localStorage.getItem("cpdocs-api-"+k+"-width");if(v)document.documentElement.style.setProperty("--api-"+k+"-width",v+"px")}}catch(e){}try{const t=localStorage.getItem("cpdocs-api-theme");document.documentElement.dataset.theme=t==="dark"||t==="light"?t:(matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light")}catch(e){}
