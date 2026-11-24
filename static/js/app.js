document.addEventListener("input", function (event) {
  var input = event.target;
  if (!input.classList || !input.classList.contains("select-filter")) {
    return;
  }
  var root = input.form || input.closest("form") || document;
  var select = root.querySelector(input.getAttribute("data-select"));
  if (!select) {
    return;
  }
  var query = input.value.trim().toLowerCase();
  Array.prototype.forEach.call(select.options, function (option) {
    if (!option.value) {
      option.hidden = false;
      return;
    }
    option.hidden = Boolean(query && option.text.toLowerCase().indexOf(query) === -1);
  });
});
