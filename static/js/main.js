document.addEventListener("DOMContentLoaded", () => {
    const menuToggle = document.getElementById("menuToggle");
    const navLinks = document.getElementById("navLinks");

    if (menuToggle && navLinks) {
        menuToggle.addEventListener("click", () => {
            const isOpen = navLinks.classList.toggle("open");

            menuToggle.setAttribute(
                "aria-expanded",
                String(isOpen)
            );
        });
    }

    document.querySelectorAll(".alert-close").forEach((button) => {
        button.addEventListener("click", () => {
            const alert = button.closest(".alert");

            if (alert) {
                alert.remove();
            }
        });
    });
});