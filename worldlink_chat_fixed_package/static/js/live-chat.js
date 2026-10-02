(function () {
    'use strict';

    const CONVERSATION_KEY = 'worldlink_chat_conversation';
    const NAME_KEY = 'worldlink_chat_name';
    const EMAIL_KEY = 'worldlink_chat_email';
    const TRACKING_KEY = 'worldlink_chat_tracking';

    let conversationId = localStorage.getItem(CONVERSATION_KEY) || '';
    let pollingTimer = null;
    let sending = false;
    let lastRenderedId = 0;

    function el(id) {
        return document.getElementById(id);
    }

    function saveCustomerDetails() {
        const name = el('wl-chat-name');
        const email = el('wl-chat-email');
        const tracking = el('wl-chat-tracking');

        if (name && name.value.trim()) {
            localStorage.setItem(NAME_KEY, name.value.trim());
        }
        if (email && email.value.trim()) {
            localStorage.setItem(EMAIL_KEY, email.value.trim());
        }
        if (tracking && tracking.value.trim()) {
            localStorage.setItem(TRACKING_KEY, tracking.value.trim());
        }
    }

    function restoreCustomerDetails() {
        const name = el('wl-chat-name');
        const email = el('wl-chat-email');
        const tracking = el('wl-chat-tracking');

        if (name) name.value = localStorage.getItem(NAME_KEY) || '';
        if (email) email.value = localStorage.getItem(EMAIL_KEY) || '';
        if (tracking) tracking.value = localStorage.getItem(TRACKING_KEY) || '';

        updateDetailsState();
    }

    function updateDetailsState() {
        const details = el('wl-chat-details');
        const name = el('wl-chat-name');
        const email = el('wl-chat-email');
        const tracking = el('wl-chat-tracking');

        if (!details) return;

        const hasConversation = Boolean(conversationId);
        const hasSavedIdentity = Boolean(
            localStorage.getItem(NAME_KEY) &&
            localStorage.getItem(EMAIL_KEY)
        );

        if (hasConversation && hasSavedIdentity) {
            details.classList.add('compact');
            if (name) name.required = false;
            if (email) email.required = false;
            if (tracking) tracking.required = false;
        } else {
            details.classList.remove('compact');
            if (name) name.required = true;
            if (email) email.required = true;
        }
    }

    function formatTime(value) {
        if (!value) return '';
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return '';
        return date.toLocaleTimeString([], {
            hour: 'numeric',
            minute: '2-digit'
        });
    }

    function renderMessages(messages) {
        const box = el('wl-chat-messages');
        if (!box) return;

        if (!Array.isArray(messages) || messages.length === 0) {
            box.innerHTML = `
                <div class="wl-chat-welcome">
                    <strong>How can we help?</strong>
                    <p>Send us a message and our support team will get back to you.</p>
                </div>`;
            return;
        }

        box.innerHTML = '';

        messages.forEach(function (item) {
            const row = document.createElement('div');
            row.className = 'wl-chat-message-row ' +
                (item.sender_type === 'admin' ? 'from-support' : 'from-customer');

            const bubble = document.createElement('div');
            bubble.className = 'wl-chat-bubble';

            const text = document.createElement('div');
            text.textContent = item.message || '';

            const meta = document.createElement('small');
            meta.textContent =
                (item.sender_type === 'admin' ? 'Worldlink Support' : 'You') +
                (formatTime(item.created_at) ? ' · ' + formatTime(item.created_at) : '');

            bubble.appendChild(text);
            bubble.appendChild(meta);
            row.appendChild(bubble);
            box.appendChild(row);
        });

        box.scrollTop = box.scrollHeight;

        const newest = messages[messages.length - 1];
        if (newest && newest.id) lastRenderedId = newest.id;
    }

    async function loadMessages() {
        if (!conversationId) return;

        try {
            const response = await fetch(
                '/api/chat/' + encodeURIComponent(conversationId),
                {
                    cache: 'no-store',
                    headers: { 'Accept': 'application/json' }
                }
            );

            if (!response.ok) return;

            const data = await response.json();
            if (!data.success && !data.ok) return;

            renderMessages(data.messages || []);
        } catch (error) {
            // Keep the chat open if a temporary request fails.
        }
    }

    function startPolling() {
        if (pollingTimer) return;
        loadMessages();
        pollingTimer = setInterval(loadMessages, 2000);
    }

    function stopPolling() {
        if (pollingTimer) {
            clearInterval(pollingTimer);
            pollingTimer = null;
        }
    }

    window.openWorldlinkChat = function (event) {
        if (event) event.preventDefault();

        const panel = el('worldlink-chat-panel');
        const launcher = el('worldlink-chat-launcher');
        if (!panel) return;

        restoreCustomerDetails();

        panel.classList.add('open');
        panel.setAttribute('aria-hidden', 'false');
        if (launcher) launcher.classList.add('hidden');

        startPolling();

        const message = el('wl-chat-message');
        if (message) {
            setTimeout(function () {
                message.focus();
            }, 100);
        }
    };

    window.closeWorldlinkChat = function () {
        const panel = el('worldlink-chat-panel');
        const launcher = el('worldlink-chat-launcher');

        if (panel) {
            panel.classList.remove('open');
            panel.setAttribute('aria-hidden', 'true');
        }

        if (launcher) launcher.classList.remove('hidden');
        stopPolling();
    };

    window.sendWorldlinkMessage = async function (event) {
        event.preventDefault();

        if (sending) return;

        const form = el('wl-chat-form');
        const button = form ? form.querySelector('button[type="submit"]') : null;
        const name = el('wl-chat-name');
        const email = el('wl-chat-email');
        const tracking = el('wl-chat-tracking');
        const message = el('wl-chat-message');

        if (!message || !message.value.trim()) return;

        const savedName = localStorage.getItem(NAME_KEY) || '';
        const savedEmail = localStorage.getItem(EMAIL_KEY) || '';
        const savedTracking = localStorage.getItem(TRACKING_KEY) || '';

        const customerName = (name && name.value.trim()) || savedName;
        const customerEmail = (email && email.value.trim()) || savedEmail;
        const trackingNumber = (tracking && tracking.value.trim()) || savedTracking;

        if (!customerName || !customerEmail) {
            if (name) name.focus();
            return;
        }

        sending = true;
        if (button) {
            button.disabled = true;
            button.textContent = 'Sending...';
        }

        try {
            const response = await fetch('/chat/send', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                body: JSON.stringify({
                    conversation_id: conversationId,
                    customer_name: customerName,
                    customer_email: customerEmail,
                    tracking_number: trackingNumber,
                    message: message.value.trim()
                })
            });

            const data = await response.json();

            if (!response.ok || (!data.success && !data.ok)) {
                throw new Error(data.error || 'Message could not be sent.');
            }

            conversationId = data.conversation_id || conversationId;
            localStorage.setItem(CONVERSATION_KEY, conversationId);
            localStorage.setItem(NAME_KEY, customerName);
            localStorage.setItem(EMAIL_KEY, customerEmail);
            if (trackingNumber) {
                localStorage.setItem(TRACKING_KEY, trackingNumber);
            }

            message.value = '';
            updateDetailsState();
            await loadMessages();
            startPolling();

        } catch (error) {
            alert(error.message || 'Unable to send your message. Please try again.');
        } finally {
            sending = false;
            if (button) {
                button.disabled = false;
                button.textContent = 'Send';
            }
        }
    };

    document.addEventListener('DOMContentLoaded', function () {
        restoreCustomerDetails();
    });
})();
