
document.addEventListener("DOMContentLoaded", () => {
    // Close success and error messages.
    document.querySelectorAll(".alert-close").forEach((button) => {
        button.addEventListener("click", () => {
            button.closest(".alert").remove();
        });
    });

    // Update the minimum initial deposit when account type changes.
    const accountForm = document.querySelector("#account-form");

    if (accountForm) {
        const balanceInput = accountForm.querySelector('[name="balance"]');
        const hint = document.querySelector("#minimum-hint");

        accountForm.querySelectorAll('[name="account_type"]').forEach((radio) => {
            radio.addEventListener("change", () => {
                const minimum = Number(radio.dataset.minimum);

                balanceInput.min = minimum;
                hint.textContent =
                    `Minimum initial deposit: ₹${minimum.toLocaleString("en-IN")}`;
            });
        });

        accountForm.addEventListener("submit", (event) => {
            const selected = accountForm.querySelector(
                '[name="account_type"]:checked'
            );

            if (!selected) {
                event.preventDefault();
                alert("Please select an account type.");
                return;
            }

            const minimum = Number(selected.dataset.minimum);
            const balance = Number(balanceInput.value);

            if (balance < minimum) {
                event.preventDefault();
                alert(`Minimum deposit for this account is ₹${minimum}.`);
            }
        });
    }

    // Confirm before sending a demo transfer.
    const transferForm = document.querySelector("#transfer-form");

    if (transferForm) {
        transferForm.addEventListener("submit", (event) => {
            const sender = transferForm.querySelector(
                '[name="from_account"]'
            ).value.trim();

            const receiver = transferForm.querySelector(
                '[name="to_account"]'
            ).value.trim();

            const amount = Number(
                transferForm.querySelector('[name="amount"]').value
            );

            if (sender === receiver) {
                event.preventDefault();
                alert("Sender and receiver must be different accounts.");
                return;
            }

            if (!Number.isFinite(amount) || amount <= 0) {
                event.preventDefault();
                alert("Enter a valid transfer amount.");
                return;
            }

            if (!window.confirm(
                `Confirm demo transfer of ₹${amount.toLocaleString("en-IN", {
                    minimumFractionDigits: 2
                })}?`
            )) {
                event.preventDefault();
            }
        });
    }
});
