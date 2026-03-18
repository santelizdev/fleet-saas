(function () {
  function buildOptions(select, options) {
    const currentValue = select.value;
    select.innerHTML = "";

    const emptyOption = document.createElement("option");
    emptyOption.value = "";
    emptyOption.textContent = "---------";
    select.appendChild(emptyOption);

    let hasCurrent = false;
    options.forEach((option) => {
      const element = document.createElement("option");
      element.value = option.value;
      element.textContent = option.label;
      if (String(option.value) === String(currentValue)) {
        element.selected = true;
        hasCurrent = true;
      }
      select.appendChild(element);
    });

    if (!hasCurrent) {
      select.value = "";
    }
  }

  function loadOptions(companyField, dependentField) {
    const companyId = companyField.value;
    if (!companyId) {
      buildOptions(dependentField, []);
      dependentField.disabled = true;
      return;
    }

    const url = new URL(dependentField.dataset.optionsUrl, window.location.origin);
    url.searchParams.set("field", dependentField.dataset.fieldName);
    url.searchParams.set("company_id", companyId);

    fetch(url, { headers: { "X-Requested-With": "XMLHttpRequest" } })
      .then((response) => response.json())
      .then((payload) => {
        buildOptions(dependentField, payload.options || []);
        dependentField.disabled = false;
      });
  }

  function initCompanyDependencies() {
    const companyField = document.getElementById("id_company");
    if (!companyField) {
      return;
    }

    const dependentFields = Array.from(document.querySelectorAll("select[data-company-dependent='1']"));
    if (!dependentFields.length) {
      return;
    }

    dependentFields.forEach((field) => {
      if (!companyField.value) {
        buildOptions(field, []);
        field.disabled = true;
      } else {
        loadOptions(companyField, field);
      }
    });

    companyField.addEventListener("change", function () {
      dependentFields.forEach((field) => loadOptions(companyField, field));
    });
  }

  document.addEventListener("DOMContentLoaded", initCompanyDependencies);
})();
