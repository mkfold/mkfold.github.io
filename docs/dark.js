// hacked up by mia k

const UNDARK_TEXT = "light";  // "☀️";
const DARK_TEXT = "dark";  // "🌕";

const _get_dark_state = () => {
    return localStorage.getItem("darkmode_enabled") || "n";
}
const _set_button_text = enabled => {
    const b = document.getElementById("dark-button");
    const c = (enabled == "y" ? UNDARK_TEXT : DARK_TEXT);
    if (b != null) b.textContent = c;
}
const _darken = () => {
    const b = document.body;
    b.classList.toggle("dark");
    for (x of b.getElementsByClassName("card")) { x.classList.toggle("dark"); }
}
const toggle_dark = () => {
    const e = (_get_dark_state() == "y" ? "n" : "y");
    localStorage.setItem("darkmode_enabled", e);
    _darken();
    _set_button_text(e);
}
const dark_init = () => {
    const e = _get_dark_state();
    if (e == "y") _darken();

    const b = document.createElement("span");
    b.id = "dark-button";
    b.onclick = toggle_dark;

    const f = document.body.getElementsByTagName("div");
    if ("header" in f) f.header.prepend(b);

    _set_button_text(e);
}
window.onload = () => { dark_init(); }