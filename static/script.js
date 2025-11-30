/*
    KABM (कृषि मित्र) के लिए मुख्य JavaScript फ़ाइल
    - AI चैटबॉट (Chatbot) लॉजिक (TTS + Mute (म्यूट) Control (कंट्रोल) के साथ)
    - "उन्नतशील खेती" (Modern Farming) पेज के लिए 'AI Ask' बटन लॉजिक
*/

// --- 1. AI चैटबॉट (AI Chatbot) लॉजिक ---
document.addEventListener('DOMContentLoaded', () => {

    // --- A. AI चैटबॉट (Chatbot) UI को ढूँढें ---
    const chatbotToggle = document.getElementById('chatbot-toggle');
    const chatbotWindow = document.getElementById('chatbot-window');
    const chatBody = document.getElementById('chat-body'); // Ensure this ID matches layout.html
    const messageInput = document.getElementById('chat-input');
    const sendButton = document.getElementById('chat-send-btn'); 
    const closeButton = document.getElementById('chatbot-close-btn');
    const languageSelect = document.getElementById('tts-language-select');
    const muteButton = document.getElementById('tts-mute-btn');
    
    // Mute Icon ढूँढें (सुरक्षित तरीके से)
    let muteIcon = null;
    if (muteButton) {
        muteIcon = muteButton.querySelector('i');
    }

    // Mute State Variable
    let isMuted = false;

    // --- Event Listeners सेट करें ---
    if (chatbotToggle && chatbotWindow) {
        
        // 1. चैटबॉट खोलें
        chatbotToggle.addEventListener('click', () => {
            chatbotWindow.classList.add('open'); 
            // पेंडिंग सवाल चेक करें (Modern Farming पेज से)
            const pendingQuestion = chatbotToggle.dataset.pendingQuestion;
            if (pendingQuestion) {
                sendQuestionToAI(pendingQuestion);
                chatbotToggle.dataset.pendingQuestion = ""; 
            }
        });

        // 2. चैटबॉट बंद करें
        if (closeButton) {
            closeButton.addEventListener('click', () => {
                chatbotWindow.classList.remove('open');
                if ('speechSynthesis' in window) {
                    speechSynthesis.cancel(); // बोलना बंद करें
                }
            });
        }

        // 3. "Send" बटन क्लिक
        if (sendButton && messageInput) {
            sendButton.addEventListener('click', () => {
                const messageText = messageInput.value.trim();
                if (messageText) {
                    sendQuestionToAI(messageText);
                    messageInput.value = '';
                }
            });

            // 4. "Enter" की प्रेस
            messageInput.addEventListener('keypress', (event) => {
                if (event.key === 'Enter') {
                    const messageText = messageInput.value.trim();
                    if (messageText) {
                        sendQuestionToAI(messageText);
                        messageInput.value = '';
                    }
                }
            });
        }

        // 5. Mute बटन लॉजिक
        if (muteButton && muteIcon) {
            muteButton.addEventListener('click', () => {
                isMuted = !isMuted; // टॉगल करें
                
                if (isMuted) {
                    // म्यूट करें
                    if ('speechSynthesis' in window) {
                        speechSynthesis.cancel();
                    }
                    muteIcon.classList.remove('fa-volume-high');
                    muteIcon.classList.add('fa-volume-xmark'); // म्यूट आइकन (FontAwesome 6)
                    // Fallback for FontAwesome 5 if needed: fa-volume-mute
                    if (!muteIcon.classList.contains('fa-volume-xmark')) {
                         muteIcon.classList.add('fa-volume-mute');
                    }
                    muteButton.setAttribute('aria-label', 'Unmute audio');
                } else {
                    // अनम्यूट करें
                    muteIcon.classList.remove('fa-volume-xmark');
                    muteIcon.classList.remove('fa-volume-mute');
                    muteIcon.classList.add('fa-volume-high');
                    muteButton.setAttribute('aria-label', 'Mute audio');
                }
            });
        }
    }

    // --- B. AI को सवाल भेजने का फंक्शन ---
    async function sendQuestionToAI(question) {
        if (!chatBody) return; // सुरक्षा जांच

        // 1. यूज़र का मैसेज दिखाएँ
        addMessageToChat('user', question);

        // 2. लोडिंग इंडिकेटर दिखाएँ
        const loadingIndicator = addMessageToChat('bot', 'loading');
        
        try {
            // 3. सर्वर (app.py) को कॉल करें
            const response = await fetch('/ask-ai', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: question })
            });

            if (!response.ok) {
                const errorData = await response.json();
                const errorMessage = errorData.answer || 'क्षमा करें, AI से कनेक्ट करने में समस्या हुई।';
                loadingIndicator.innerHTML = errorMessage;
                loadingIndicator.classList.remove('loading-indicator'); // लोडिंग क्लास हटाएँ
                speakText(errorMessage);
                return;
            }

            const data = await response.json();
            
            // 4. जवाब दिखाएँ
            const answerText = data.answer;
            // HTML रेंडर करें (bold, italic आदि)
            loadingIndicator.innerHTML = simpleMarkdownToHtml(answerText);
            loadingIndicator.classList.remove('loading-indicator'); // लोडिंग क्लास हटाएँ
            
            // 5. जवाब बोलें (Speak)
            // साफ टेक्स्ट (बिना HTML tags के) बोलें
            speakText(cleanTextForSpeech(answerText));

        } catch (error) {
            console.error('Fetch Error:', error);
            const errorMsg = 'क्षमा करें, सर्वर से कनेक्ट नहीं हो पा रहा है।';
            loadingIndicator.textContent = errorMsg;
            loadingIndicator.classList.remove('loading-indicator');
            speakText(errorMsg);
        }
    }

    // --- C. चैट में मैसेज जोड़ने का फंक्शन ---
    function addMessageToChat(sender, content) {
        if (!chatBody) return null;

        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}`; 
        
        if (content === 'loading') {
            messageDiv.classList.add('loading-indicator');
            // 3 डॉट्स एनिमेशन
            messageDiv.innerHTML = '<span></span><span></span><span></span>';
        } else if (sender === 'user') {
            messageDiv.textContent = content;
        } else { 
            // Bot मैसेज HTML हो सकता है
            messageDiv.innerHTML = content;
        }
        
        chatBody.appendChild(messageDiv);
        chatBody.scrollTop = chatBody.scrollHeight; // नीचे स्क्रॉल करें
        return messageDiv;
    }

    // --- D. Markdown को HTML में बदलने का फंक्शन ---
    function simpleMarkdownToHtml(text) {
        if (!text) return "";
        // **Bold**
        text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        // *Italic*
        text = text.replace(/\*(.*?)\*/g, '<em>$1</em>');
        // New line -> <br>
        text = text.replace(/\n/g, '<br>');
        return text;
    }

    // --- E. टेक्स्ट बोलने का फंक्शन (TTS) ---
    function speakText(text) {
        if (isMuted) return; // अगर म्यूट है तो न बोलें
        if (!('speechSynthesis' in window)) return; // अगर ब्राउज़र सपोर्ट नहीं करता
        
        speechSynthesis.cancel(); // पुराना बोलना बंद करें
        
        const utterance = new SpeechSynthesisUtterance(text);
        
        // लैंग्वेज सेलेक्ट करें
        if (languageSelect) {
            utterance.lang = languageSelect.value;
        } else {
            utterance.lang = 'hi-IN'; // डिफ़ॉल्ट हिंदी
        }
        
        utterance.rate = 1.0; // स्पीड
        utterance.pitch = 1.0; // पिच
        
        speechSynthesis.speak(utterance);
    }

    // --- F. बोलने के लिए टेक्स्ट साफ करने का फंक्शन ---
    function cleanTextForSpeech(text) {
        if (!text) return "";
        // स्टार्स (*) हटाएँ
        text = text.replace(/\*/g, '');
        // एक्स्ट्रा स्पेस हटाएँ
        text = text.replace(/\s+/g, ' ').trim();
        return text;
    }


    // --- 2. "उन्नतशील खेती" पेज के बटन लॉजिक ---
    const aiAskButtons = document.querySelectorAll('.ai-ask-button');
    
    aiAskButtons.forEach(button => {
        button.addEventListener('click', (event) => {
            event.preventDefault(); 
            const question = button.dataset.ask;
            
            if (question) {
                // अगर चैटबॉट बंद है, तो खोलें
                if (chatbotWindow && !chatbotWindow.classList.contains('open')) {
                    if (chatbotToggle) {
                        chatbotToggle.dataset.pendingQuestion = question;
                        chatbotToggle.click(); // क्लिक ट्रिगर करें
                    }
                } else {
                    // अगर पहले से खुला है, तो सीधे भेजें
                    sendQuestionToAI(question);
                }
            }
        });
    });

});
