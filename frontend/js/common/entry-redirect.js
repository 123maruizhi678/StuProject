import { MODULES, moduleEntry } from "./modules.js";

const module = MODULES.find(item => item.id === document.body.dataset.module);
location.replace(moduleEntry(module || {}) || "/");
