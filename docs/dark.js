// hacked up by mia k

const SUN_SYMBOL = "☀️";
const MOON_SYMBOL = "🌕";
const _set_button_text = enabled => {
    var b = document.getElementById("dark-button");
    const c = (enabled == "y" ? SUN_SYMBOL : MOON_SYMBOL);
    if (b != null) b.textContent = c;
}
const _darken = () => {
    var b = document.body;
    b.classList.toggle("darken");
    for (x of b.getElementsByClassName("card")) { x.classList.toggle("darken"); }
    for (x of b.getElementsByTagName("code")) { x.classList.toggle("darken"); }
    for (x of b.getElementsByTagName("pre")) { x.classList.toggle("darken"); }
}
const toggle_dark = () => {
    var e = localStorage.getItem("darkmode_enabled") || "n";
    e = (e == "y" ? "n" : "y");
    localStorage.setItem("darkmode_enabled", e);
    _darken();
    _set_button_text(enabled);
}
const dark_init = () => {
    let b = document.createElement("div");
    b.id = "dark-button";
    b.onclick = toggle_dark;
    document.body.prepend(b);

    const e = localStorage.getItem("darkmode_enabled") || "n";
    if (e == "y") _darken();
    _set_button_text(e);
}
window.onload = () => { dark_init(); }