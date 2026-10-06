/* =========================================================
   WORLDLINK COURIER SERVICE
   LIVE CHAT
   ========================================================= */

(function () {

    "use strict";

    const STORAGE_KEY = "worldlink_chat_conversation";

    let conversationId = "";
    let customerName = "";
    let customerEmail = "";
    let trackingNumber = "";
    let isSending = false;


    /* =====================================================
       ELEMENT HELPERS
       ===================================================== */

    function getPanel() {
        return document.getElementById("worldlink-chat-panel");
    }

    function getLauncher() {
        return document.getElementById("worldlink-chat-launcher");
    }

    function getForm() {
        const panel = getPanel();
        if (!panel) return null;

        return panel.querySelector("form");
    }

    function getNameField() {
        const panel = getPanel();
        if (!panel) return null;

        return (
            panel.querySelector('input[name="name"]') ||
            panel.querySelector('input[name="customer_name"]') ||
            panel.querySelector("#worldlink-chat-name")
        );
    }

    function getEmailField() {
        const panel = getPanel();
        if (!panel) return null;

        return (
            panel.querySelector('input[name="email"]') ||
            panel.querySelector('input[name="customer_email"]') ||
            panel.querySelector("#worldlink-chat-email")
        );
    }

    function getTrackingField() {
        const panel = getPanel();
        if (!panel) return null;

        return (
            panel.querySelector('input[name="tracking_number"]') ||
            panel.querySelector("#worldlink-chat-tracking")
        );
    }

    function getMessageField() {
        const panel = getPanel();
        if (!panel) return null;

        return (
            panel.querySelector('textarea[name="message"]') ||
            panel.querySelector("#worldlink-chat-message") ||
            panel.querySelector("textarea")
        );
    }

    function getMessagesArea() {
        const panel = getPanel();
        if (!panel) return null;

        return (
            panel.querySelector("#worldlink-chat-messages") ||
            panel.querySelector(".worldlink-chat-messages") ||
            panel.querySelector(".chat-messages")
        );
    }


    /* =====================================================
       LOCAL STORAGE
       ===================================================== */

    function loadConversation() {

        try {

            const saved = localStorage.getItem(STORAGE_KEY);

            if (!saved) {
                return;
            }

            const data = JSON.parse(saved);

            conversationId = data.conversationId || "";
            customerName = data.customerName || "";
            customerEmail = data.customerEmail || "";
            trackingNumber = data.trackingNumber || "";

        } catch (error) {

            console.warn(
                "Worldlink Chat storage error:",
                error
            );

        }
    }


    function saveConversation() {

        try {

            localStorage.setItem(
                STORAGE_KEY,
                JSON.stringify({
                    conversationId: conversationId,
                    customerName: customerName,
                    customerEmail: customerEmail,
                    trackingNumber: trackingNumber
                })
            );

        } catch (error) {

            console.warn(
                "Worldlink Chat save error:",
                error
            );

        }
    }


    /* =====================================================
       RESTORE CUSTOMER DETAILS
       ===================================================== */

    function restoreCustomerDetails() {

        const name = getNameField();
        const email = getEmailField();
        const tracking = getTrackingField();

        if (name && customerName) {
            name.value = customerName;
        }

        if (email && customerEmail) {
            email.value = customerEmail;
        }

        if (tracking && trackingNumber) {
            tracking.value = trackingNumber;
        }
    }


    /* =====================================================
       HIDE ONLY CUSTOMER INFORMATION FIELDS
       
       IMPORTANT:
       Do NOT hide the parent form.
       The message textarea and Send button
       must remain available.
       ===================================================== */

    function hideCustomerDetails() {

        hideSingleCustomerField(getNameField());
        hideSingleCustomerField(getEmailField());
        hideSingleCustomerField(getTrackingField());

        showActiveConversationNotice();
    }


    function hideSingleCustomerField(field) {

        if (!field) {
            return;
        }

        /*
         * Only hide a dedicated field wrapper if one exists.
         *
         * Never use field.parentElement blindly because
         * the parent may be the entire chat form.
         */

        const wrapper =
            field.closest(".worldlink-chat-field");

        if (wrapper) {

            wrapper.style.display = "none";
            wrapper.dataset.worldlinkHidden = "true";

        } else {

            field.style.display = "none";
            field.dataset.worldlinkHidden = "true";

        }
    }


    /* =====================================================
       SHOW CUSTOMER INFORMATION FIELDS
       ===================================================== */

    function showCustomerDetails() {

        const hiddenWrappers =
            document.querySelectorAll(
                '[data-worldlink-hidden="true"]'
            );

        hiddenWrappers.forEach(function (element) {

            element.style.display = "";

            delete element.dataset.worldlinkHidden;

        });


        const notice =
            document.getElementById(
                "worldlink-chat-active-notice"
            );

        if (notice) {
            notice.remove();
        }
    }


    /* =====================================================
       ACTIVE CONVERSATION NOTICE
       ===================================================== */

    function showActiveConversationNotice() {

        const chatForm = getForm();

        if (!chatForm) {
            return;
        }

        if (
            document.getElementById(
                "worldlink-chat-active-notice"
            )
        ) {
            return;
        }

        const notice =
            document.createElement("div");

        notice.id =
            "worldlink-chat-active-notice";

        notice.style.cssText = `
            padding: 8px 10px;
            margin-bottom: 8px;
            border-radius: 8px;
            background: #eef6ff;
            border: 1px solid #d7e8ff;
            color: #315274;
            font-size: 10px;
            line-height: 1.4;
        `;

        notice.innerHTML = `
            <strong style="color:#155eef;">
                Active conversation
            </strong>
            <br>
            You can continue messaging Worldlink Support.
        `;

        /*
         * Put the notice immediately before
         * the message field instead of at the
         * very beginning of the form.
         */

        const messageField = getMessageField();

        if (messageField) {

            messageField.parentElement.insertBefore(
                notice,
                messageField
            );

        } else {

            chatForm.insertBefore(
                notice,
                chatForm.firstChild
            );

        }
    }


    /* =====================================================
       OPEN CHAT
       ===================================================== */

    function openWorldlinkChat() {

        const panel = getPanel();

        if (!panel) {

            console.error(
                "Worldlink Chat: chat panel not found."
            );

            return;
        }

        panel.classList.add("open");

        panel.setAttribute(
            "aria-hidden",
            "false"
        );

        panel.style.display = "flex";
        panel.style.visibility = "visible";
        panel.style.opacity = "1";
        panel.style.pointerEvents = "auto";


        restoreCustomerDetails();


        if (conversationId) {

            hideCustomerDetails();

            loadMessages();

        }


        setTimeout(function () {

            const messageField =
                getMessageField();

            if (messageField) {
                messageField.focus();
            }

            scrollToBottom();

        }, 150);
    }


    /* =====================================================
       CLOSE CHAT
       ===================================================== */

    function closeWorldlinkChat() {

        const panel = getPanel();

        if (!panel) {
            return;
        }

        panel.classList.remove("open");

        panel.setAttribute(
            "aria-hidden",
            "true"
        );

        panel.style.display = "none";
        panel.style.visibility = "hidden";
        panel.style.opacity = "0";
        panel.style.pointerEvents = "none";
    }


    /* =====================================================
       TOGGLE CHAT
       ===================================================== */

    function toggleWorldlinkChat() {

        const panel = getPanel();

        if (!panel) {
            return;
        }

        if (
            panel.classList.contains("open")
        ) {

            closeWorldlinkChat();

        } else {

            openWorldlinkChat();

        }
    }


    /* =====================================================
       CLOSE BUTTON
       ===================================================== */

    function setupCloseButton() {

        const panel = getPanel();

        if (!panel) {
            return;
        }

        const closeButton =
            panel.querySelector(
                "#worldlink-chat-close"
            ) ||
            panel.querySelector(
                ".worldlink-chat-close"
            ) ||
            panel.querySelector(
                "[data-chat-close]"
            ) ||
            panel.querySelector(
                'button[aria-label="Close"]'
            );

        if (!closeButton) {
            return;
        }

        if (
            closeButton.dataset.worldlinkReady ===
            "true"
        ) {
            return;
        }

        closeButton.dataset.worldlinkReady =
            "true";

        closeButton.addEventListener(
            "click",
            function (event) {

                event.preventDefault();
                event.stopPropagation();

                closeWorldlinkChat();

            }
        );
    }


    /* =====================================================
       SEND MESSAGE
       ===================================================== */

    async function sendMessage(event) {

        event.preventDefault();

        if (isSending) {
            return;
        }


        const messageField =
            getMessageField();

        if (!messageField) {

            console.error(
                "Worldlink Chat: message field not found."
            );

            return;
        }


        const message =
            messageField.value.trim();


        if (!message) {

            messageField.focus();

            return;
        }


        /*
         * Only collect customer details
         * when starting a NEW conversation.
         */

        if (!conversationId) {

            const nameField =
                getNameField();

            const emailField =
                getEmailField();

            const trackingField =
                getTrackingField();


            customerName =
                nameField
                    ? nameField.value.trim()
                    : "";


            customerEmail =
                emailField
                    ? emailField.value.trim()
                    : "";


            trackingNumber =
                trackingField
                    ? trackingField.value
                        .trim()
                        .toUpperCase()
                    : "";


            if (!customerName) {

                alert(
                    "Please enter your name."
                );

                if (nameField) {
                    nameField.focus();
                }

                return;
            }


            if (!customerEmail) {

                alert(
                    "Please enter your email address."
                );

                if (emailField) {
                    emailField.focus();
                }

                return;
            }
        }


        isSending = true;


        const chatForm =
            getForm();

        const submitButton =
            chatForm
                ? chatForm.querySelector(
                    'button[type="submit"]'
                )
                : null;


        const originalText =
            submitButton
                ? submitButton.textContent
                : "Send Message";


        if (submitButton) {

            submitButton.disabled =
                true;

            submitButton.textContent =
                "Sending...";

        }


        try {

            const response =
                await fetch(
                    "/chat/send",
                    {
                        method: "POST",

                        headers: {
                            "Content-Type":
                                "application/json"
                        },

                        body:
                            JSON.stringify({

                                conversation_id:
                                    conversationId,

                                name:
                                    customerName,

                                email:
                                    customerEmail,

                                tracking_number:
                                    trackingNumber,

                                message:
                                    message
                            })
                    }
                );


            const data =
                await response.json();


            if (!response.ok) {

                throw new Error(
                    data.error ||
                    "Unable to send message."
                );

            }


            /*
             * IMPORTANT:
             * Flask returns "ok", not "success".
             */

            if (!data.ok) {

                throw new Error(
                    data.error ||
                    "Unable to send message."
                );

            }


            /*
             * Save conversation ID.
             */

            conversationId =
                data.conversation_id;


            saveConversation();


            /*
             * Clear ONLY the message box.
             */

            messageField.value =
                "";


            /*
             * Hide name/email/tracking,
             * but KEEP message box and
             * Send button visible.
             */

            hideCustomerDetails();


            await loadMessages();


            messageField.focus();


        } catch (error) {

            console.error(
                "Worldlink Chat error:",
                error
            );

            alert(
                error.message ||
                "Unable to send your message."
            );

        } finally {

            isSending = false;


            if (submitButton) {

                submitButton.disabled =
                    false;

                submitButton.textContent =
                    originalText ||
                    "Send Message";

            }

        }
    }


    /* =====================================================
       LOAD CHAT MESSAGES
       ===================================================== */

    async function loadMessages() {

        if (!conversationId) {
            return;
        }


        try {

            const response =
                await fetch(
                    "/api/chat/" +
                    encodeURIComponent(
                        conversationId
                    ) +
                    "?t=" +
                    Date.now(),
                    {
                        cache: "no-store"
                    }
                );


            if (!response.ok) {
                return;
            }


            const data =
                await response.json();


            if (
                !data ||
                !Array.isArray(
                    data.messages
                )
            ) {
                return;
            }


            renderMessages(
                data.messages
            );


            hideCustomerDetails();


        } catch (error) {

            console.warn(
                "Worldlink Chat message loading error:",
                error
            );

        }
    }


    /* =====================================================
       RENDER MESSAGES
       ===================================================== */

    function renderMessages(messages) {

        const container =
            getMessagesArea();

        if (!container) {
            return;
        }


        container.innerHTML = "";


        messages.forEach(function (item) {

            const isAdmin =
                item.sender_type === "admin";


            const wrapper =
                document.createElement("div");


            wrapper.className =
                isAdmin
                    ? "worldlink-chat-message worldlink-chat-message-admin"
                    : "worldlink-chat-message worldlink-chat-message-customer";


            const bubble =
                document.createElement("div");


            bubble.className =
                "worldlink-chat-bubble";


            const text =
                document.createElement("div");


            text.className =
                "worldlink-chat-text";


            text.textContent =
                item.message || "";


            const time =
                document.createElement("small");


            time.className =
                "worldlink-chat-time";


            time.textContent =
                isAdmin
                    ? "Worldlink Support • " +
                      formatTime(
                          item.created_at
                      )
                    : "You • " +
                      formatTime(
                          item.created_at
                      );


            bubble.appendChild(text);

            bubble.appendChild(time);

            wrapper.appendChild(bubble);

            container.appendChild(wrapper);

        });


        scrollToBottom();
    }


    /* =====================================================
       FORMAT TIME
       ===================================================== */

    function formatTime(value) {

        if (!value) {
            return "";
        }


        const date =
            new Date(value);


        if (
            Number.isNaN(
                date.getTime()
            )
        ) {
            return "";
        }


        return date.toLocaleTimeString(
            [],
            {
                hour: "numeric",
                minute: "2-digit"
            }
        );
    }


    /* =====================================================
       SCROLL TO BOTTOM
       ===================================================== */

    function scrollToBottom() {

        const container =
            getMessagesArea();

        if (!container) {
            return;
        }


        setTimeout(function () {

            container.scrollTop =
                container.scrollHeight;

        }, 50);
    }


    /* =====================================================
       START NEW CONVERSATION
       ===================================================== */

    function startNewChat() {

        conversationId = "";
        customerName = "";
        customerEmail = "";
        trackingNumber = "";


        try {

            localStorage.removeItem(
                STORAGE_KEY
            );

        } catch (error) {

            console.warn(error);

        }


        const container =
            getMessagesArea();

        if (container) {
            container.innerHTML = "";
        }


        const messageField =
            getMessageField();

        if (messageField) {
            messageField.value = "";
        }


        showCustomerDetails();
    }


    /* =====================================================
       LAUNCHER
       ===================================================== */

    function setupLauncher() {

        const launcher =
            getLauncher();

        if (!launcher) {

            console.error(
                "Worldlink Chat launcher not found."
            );

            return;
        }


        if (
            launcher.dataset.worldlinkReady ===
            "true"
        ) {
            return;
        }


        launcher.dataset.worldlinkReady =
            "true";


        launcher.addEventListener(
            "click",
            function (event) {

                event.preventDefault();
                event.stopPropagation();

                toggleWorldlinkChat();

            }
        );
    }


    /* =====================================================
       FORM
       ===================================================== */

    function setupForm() {

        const chatForm =
            getForm();

        if (!chatForm) {
            return;
        }


        if (
            chatForm.dataset.worldlinkReady ===
            "true"
        ) {
            return;
        }


        chatForm.dataset.worldlinkReady =
            "true";


        chatForm.addEventListener(
            "submit",
            sendMessage
        );


        const messageField =
            getMessageField();


        if (messageField) {

            messageField.addEventListener(
                "keydown",
                function (event) {

                    if (
                        event.key === "Enter" &&
                        !event.shiftKey
                    ) {

                        event.preventDefault();

                        chatForm.requestSubmit();

                    }

                }
            );

        }
    }


    /* =====================================================
       POLLING FOR COMPANY REPLIES
       ===================================================== */

    function startPolling() {

        setInterval(
            function () {

                const panel =
                    getPanel();

                if (
                    conversationId &&
                    panel &&
                    panel.classList.contains(
                        "open"
                    )
                ) {

                    loadMessages();

                }

            },
            5000
        );
    }


    /* =====================================================
       INITIALIZE
       ===================================================== */

    function initialize() {

        loadConversation();

        setupLauncher();

        setupCloseButton();

        setupForm();

        restoreCustomerDetails();


        if (conversationId) {

            hideCustomerDetails();

            loadMessages();

        }


        startPolling();
    }


    /* =====================================================
       GLOBAL FUNCTIONS
       ===================================================== */

    window.openWorldlinkChat =
        openWorldlinkChat;

    window.closeWorldlinkChat =
        closeWorldlinkChat;

    window.startWorldlinkNewChat =
        startNewChat;


    /* =====================================================
       START APPLICATION
       ===================================================== */

    if (
        document.readyState ===
        "loading"
    ) {

        document.addEventListener(
            "DOMContentLoaded",
            initialize
        );

    } else {

        initialize();

    }

})();