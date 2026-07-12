/* =====================================================
   SMARTFINANCE PREMIUM UI ENGINE
===================================================== */

document.addEventListener("DOMContentLoaded", function () {

    const body = document.body;

    const themeButtons = document.querySelectorAll(
        "[data-theme-toggle]"
    );


    /* =================================================
       LOAD SAVED THEME
    ================================================= */

    const savedTheme = localStorage.getItem(
        "smartfinance-theme"
    );


    if (savedTheme === "dark") {

        body.classList.add("dark-theme");

        updateThemeButtons(true);

    } else {

        body.classList.remove("dark-theme");

        updateThemeButtons(false);

    }


    /* =================================================
       THEME TOGGLE
    ================================================= */

    themeButtons.forEach(function (button) {

        button.addEventListener(
            "click",
            function () {

                body.classList.toggle(
                    "dark-theme"
                );


                const darkModeActive =
                    body.classList.contains(
                        "dark-theme"
                    );


                if (darkModeActive) {

                    localStorage.setItem(
                        "smartfinance-theme",
                        "dark"
                    );

                } else {

                    localStorage.setItem(
                        "smartfinance-theme",
                        "light"
                    );

                }


                updateThemeButtons(
                    darkModeActive
                );

            }
        );

    });


    /* =================================================
       UPDATE THEME BUTTON TEXT
    ================================================= */

    function updateThemeButtons(
        darkModeActive
    ) {

        themeButtons.forEach(
            function (button) {

                if (darkModeActive) {

                    button.innerHTML =
                        "☀️ Light Mode";

                } else {

                    button.innerHTML =
                        "🌙 Dark Mode";

                }

            }
        );

    }


    /* =================================================
       AUTO HIDE ALERT MESSAGES
    ================================================= */

    const alerts = document.querySelectorAll(
        ".profile-message, .form-alert"
    );


    alerts.forEach(function (alert) {

        setTimeout(function () {

            alert.style.opacity = "0";

            alert.style.transform =
                "translateY(-8px)";

            alert.style.transition =
                "0.3s ease";


            setTimeout(function () {

                alert.remove();

            }, 300);

        }, 5000);

    });


    /* =================================================
       CONFIRM DELETE ACTIONS
    ================================================= */

    const deleteForms = document.querySelectorAll(
        "[data-confirm-delete]"
    );


    deleteForms.forEach(function (form) {

        form.addEventListener(
            "submit",
            function (event) {

                const message =
                    form.dataset.confirmDelete
                    || "Are you sure you want to delete this item?";


                if (!confirm(message)) {

                    event.preventDefault();

                }

            }
        );

    });


    /* =================================================
       NUMBER INPUT PROTECTION
    ================================================= */

    const numberInputs = document.querySelectorAll(
        'input[type="number"]'
    );


    numberInputs.forEach(function (input) {

        input.addEventListener(
            "input",
            function () {

                if (
                    parseFloat(input.value) < 0
                ) {

                    input.value = 0;

                }

            }
        );

    });


    /* =================================================
       BUTTON LOADING STATE
    ================================================= */

    const forms = document.querySelectorAll(
        "form"
    );


    forms.forEach(function (form) {

        form.addEventListener(
            "submit",
            function () {

                const button =
                    form.querySelector(
                        'button[type="submit"]'
                    );


                if (!button) {
                    return;
                }


                if (
                    form.dataset.noLoading === "true"
                ) {
                    return;
                }


                button.dataset.originalText =
                    button.innerHTML;


                button.innerHTML =
                    "Processing...";


                button.disabled = true;


                setTimeout(function () {

                    if (
                        button.disabled
                        && button.dataset.originalText
                    ) {

                        button.innerHTML =
                            button.dataset.originalText;

                        button.disabled = false;

                    }

                }, 8000);

            }
        );

    });


    /* =================================================
       TABLE ROW ANIMATION
    ================================================= */

    const tableRows = document.querySelectorAll(
        "tbody tr"
    );


    tableRows.forEach(
        function (row, index) {

            row.style.opacity = "0";

            row.style.transform =
                "translateY(8px)";


            setTimeout(function () {

                row.style.transition =
                    "0.35s ease";

                row.style.opacity = "1";

                row.style.transform =
                    "translateY(0)";

            }, index * 35);

        }
    );


    /* =================================================
       CARD ENTRANCE ANIMATION
    ================================================= */

    const cards = document.querySelectorAll(
        ".stat-card, "
        + ".trend-card, "
        + ".goal-preview-card, "
        + ".category-budget-card, "
        + ".admin-stat-card"
    );


    cards.forEach(
        function (card, index) {

            card.style.opacity = "0";

            card.style.transform =
                "translateY(12px)";


            setTimeout(function () {

                card.style.transition =
                    "0.4s ease";

                card.style.opacity = "1";

                card.style.transform =
                    "translateY(0)";

            }, index * 50);

        }
    );

});