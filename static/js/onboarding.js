// Interactive Onboarding System with Questions and Animations
class OnboardingManager {
    constructor() {
        this.currentStep = 0;
        this.userProfile = {
            experience: '',
            interests: [],
            goals: [],
            timeCommitment: '',
            preferredContent: []
        };
        this.steps = [
            {
                id: 'welcome',
                type: 'welcome',
                title: 'Welcome to PentraX! 🛡️',
                subtitle: 'Let\'s personalize your cybersecurity journey',
                content: 'We\'ll ask you a few questions to tailor your experience and show you the most relevant features.'
            },
            {
                id: 'experience',
                type: 'choice',
                title: 'What\'s your cybersecurity experience level?',
                subtitle: 'This helps us recommend the right content for you',
                options: [
                    { id: 'beginner', text: '🟢 Beginner', description: 'New to cybersecurity, learning the basics', icon: '🌱' },
                    { id: 'intermediate', text: '🟡 Intermediate', description: 'Some experience, looking to grow', icon: '🚀' },
                    { id: 'advanced', text: '🔴 Advanced', description: 'Experienced professional or researcher', icon: '⚡' },
                    { id: 'expert', text: '🟣 Expert', description: 'Industry veteran or specialist', icon: '👑' }
                ]
            },
            {
                id: 'interests',
                type: 'multi-choice',
                title: 'What cybersecurity areas interest you most?',
                subtitle: 'Select all that apply (you can change this later)',
                options: [
                    { id: 'penetration-testing', text: '🔓 Penetration Testing', description: 'Ethical hacking and security assessments' },
                    { id: 'malware-analysis', text: '🦠 Malware Analysis', description: 'Reverse engineering and threat analysis' },
                    { id: 'network-security', text: '🌐 Network Security', description: 'Network defense and monitoring' },
                    { id: 'web-security', text: '🌍 Web Security', description: 'Web application security and vulnerabilities' },
                    { id: 'forensics', text: '🔍 Digital Forensics', description: 'Incident response and evidence analysis' },
                    { id: 'cryptography', text: '🔐 Cryptography', description: 'Encryption and cryptographic protocols' },
                    { id: 'iot-security', text: '📱 IoT Security', description: 'Internet of Things security' },
                    { id: 'cloud-security', text: '☁️ Cloud Security', description: 'Cloud infrastructure and application security' }
                ],
                maxSelections: 4
            },
            {
                id: 'goals',
                type: 'multi-choice',
                title: 'What are your primary goals?',
                subtitle: 'What do you want to achieve on PentraX?',
                options: [
                    { id: 'learn-skills', text: '📚 Learn New Skills', description: 'Expand your cybersecurity knowledge' },
                    { id: 'build-portfolio', text: '💼 Build Portfolio', description: 'Showcase your work and projects' },
                    { id: 'network', text: '🤝 Network', description: 'Connect with other professionals' },
                    { id: 'find-opportunities', text: '💡 Find Opportunities', description: 'Discover jobs and collaborations' },
                    { id: 'share-knowledge', text: '🎓 Share Knowledge', description: 'Teach and mentor others' },
                    { id: 'research', text: '🔬 Research', description: 'Conduct security research' },
                    { id: 'monetize', text: '💰 Monetize Skills', description: 'Earn from your expertise' },
                    { id: 'stay-updated', text: '📰 Stay Updated', description: 'Keep up with latest trends' }
                ],
                maxSelections: 3
            },
            {
                id: 'time-commitment',
                type: 'choice',
                title: 'How much time can you dedicate?',
                subtitle: 'This helps us suggest the right content pace',
                options: [
                    { id: 'casual', text: '☕ Casual', description: 'A few hours per week', icon: '⏰' },
                    { id: 'regular', text: '📅 Regular', description: 'Several hours per week', icon: '📊' },
                    { id: 'dedicated', text: '🎯 Dedicated', description: 'Daily engagement', icon: '🔥' },
                    { id: 'intensive', text: '⚡ Intensive', description: 'Full-time learning/research', icon: '🚀' }
                ]
            },
            {
                id: 'content-preference',
                type: 'multi-choice',
                title: 'What type of content do you prefer?',
                subtitle: 'Select your preferred learning formats',
                options: [
                    { id: 'hands-on-labs', text: '🧪 Hands-on Labs', description: 'Interactive practical exercises' },
                    { id: 'video-tutorials', text: '🎥 Video Tutorials', description: 'Visual learning content' },
                    { id: 'written-guides', text: '📝 Written Guides', description: 'Detailed text-based tutorials' },
                    { id: 'tools-scripts', text: '🔧 Tools & Scripts', description: 'Ready-to-use security tools' },
                    { id: 'case-studies', text: '📊 Case Studies', description: 'Real-world security incidents' },
                    { id: 'discussions', text: '💬 Discussions', description: 'Community conversations' },
                    { id: 'research-papers', text: '📄 Research Papers', description: 'Academic and technical papers' },
                    { id: 'news-updates', text: '📰 News & Updates', description: 'Latest security news' }
                ],
                maxSelections: 4
            },
            {
                id: 'platform-intro',
                type: 'features',
                title: 'Discover PentraX Features',
                subtitle: 'Based on your preferences, here\'s what we recommend',
                features: []
            }
        ];
        this.init();
    }

    init() {
            this.checkOnboardingStatus();
    }

    checkOnboardingStatus() {
        const hasSeenOnboarding = localStorage.getItem('pentrax_onboarding_completed');
        const isNewUser = !localStorage.getItem('pentrax_visited');
        
        if (!hasSeenOnboarding || isNewUser) {
            setTimeout(() => this.startOnboarding(), 500);
        }
        
        localStorage.setItem('pentrax_visited', 'true');
    }

    startOnboarding() {
        this.showOnboardingModal();
    }

    showOnboardingModal() {
        const modalHTML = `
            <div class="modal fade onboarding-modal" id="onboardingModal" tabindex="-1" data-bs-backdrop="static" data-bs-keyboard="false">
                <div class="modal-dialog modal-lg modal-dialog-centered">
                    <div class="modal-content bg-gradient-dark text-white border-0">
                        <div class="modal-body p-0">
                            <div class="onboarding-container">
                                <!-- Header -->
                                <div class="onboarding-header">
                                    <div class="progress-bar-container">
                                        <div class="progress-bar" id="progressBar"></div>
                            </div>
                                    <div class="step-indicator">
                                        <span id="currentStepNumber">1</span> / <span id="totalSteps">${this.steps.length}</span>
                                </div>
                            </div>

                                <!-- Content Area -->
                                <div class="onboarding-content" id="onboardingContent">
                                    <!-- Content will be dynamically loaded here -->
                            </div>

                            <!-- Navigation -->
                                <div class="onboarding-navigation">
                                    <button class="btn btn-outline-light btn-sm" id="skipBtn" onclick="onboarding.skipOnboarding()">
                                        Skip for now
                                </button>
                                    <div class="nav-buttons">
                                        <button class="btn btn-outline-light" id="prevBtn" onclick="onboarding.prevStep()" style="display: none;">
                                            <i class="fas fa-arrow-left"></i> Back
                                </button>
                                        <button class="btn btn-primary" id="nextBtn" onclick="onboarding.nextStep()">
                                            Continue <i class="fas fa-arrow-right"></i>
                                </button>
                            </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', modalHTML);
        const modal = new bootstrap.Modal(document.getElementById('onboardingModal'));
        modal.show();
        
        // Load first step
        this.loadStep(0);
    }

    loadStep(stepIndex) {
        const step = this.steps[stepIndex];
        const contentDiv = document.getElementById('onboardingContent');
        
        // Update progress
        this.updateProgress(stepIndex);
        
        // Generate content based on step type
        let content = '';
        
        switch (step.type) {
            case 'welcome':
                content = this.generateWelcomeContent(step);
                break;
            case 'choice':
                content = this.generateChoiceContent(step);
                break;
            case 'multi-choice':
                content = this.generateMultiChoiceContent(step);
                break;
            case 'features':
                content = this.generateFeaturesContent(step);
                break;
        }
        
        // Animate content change
        contentDiv.style.opacity = '0';
        setTimeout(() => {
            contentDiv.innerHTML = content;
            contentDiv.style.opacity = '1';
            this.initializeStepInteractions(step);
        }, 300);
        
        // Update navigation
        this.updateNavigation(stepIndex);
    }

    generateWelcomeContent(step) {
        return `
            <div class="welcome-step">
                <div class="welcome-icon">
                    <div class="icon-container">
                        <i class="fas fa-shield-alt"></i>
                    </div>
                </div>
                <h2 class="step-title">${step.title}</h2>
                <p class="step-subtitle">${step.subtitle}</p>
                <div class="welcome-content">
                    <p>${step.content}</p>
                    <div class="welcome-features">
                        <div class="feature-item">
                            <i class="fas fa-users"></i>
                            <span>Join a community of cybersecurity professionals</span>
                        </div>
                        <div class="feature-item">
                            <i class="fas fa-flask"></i>
                            <span>Access hands-on labs and practical exercises</span>
                        </div>
                        <div class="feature-item">
                            <i class="fas fa-robot"></i>
                            <span>Get help from our AI assistant</span>
                        </div>
                        <div class="feature-item">
                            <i class="fas fa-store"></i>
                            <span>Monetize your expertise in the marketplace</span>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    generateChoiceContent(step) {
        const optionsHTML = step.options.map(option => `
            <div class="choice-option" data-value="${option.id}">
                <div class="option-icon">${option.icon}</div>
                <div class="option-content">
                    <div class="option-title">${option.text}</div>
                    <div class="option-description">${option.description}</div>
                </div>
                <div class="option-check">
                    <i class="fas fa-check"></i>
                </div>
            </div>
        `).join('');

        return `
            <div class="choice-step">
                <h2 class="step-title">${step.title}</h2>
                <p class="step-subtitle">${step.subtitle}</p>
                <div class="choice-options">
                    ${optionsHTML}
                </div>
            </div>
        `;
    }

    generateMultiChoiceContent(step) {
        const optionsHTML = step.options.map(option => `
            <div class="multi-choice-option" data-value="${option.id}">
                <div class="option-checkbox">
                    <i class="fas fa-check"></i>
                </div>
                <div class="option-content">
                    <div class="option-title">${option.text}</div>
                    <div class="option-description">${option.description}</div>
                </div>
            </div>
        `).join('');

        return `
            <div class="multi-choice-step">
                <h2 class="step-title">${step.title}</h2>
                <p class="step-subtitle">${step.subtitle}</p>
                <div class="selection-limit">
                    <small>Select up to ${step.maxSelections} options</small>
                </div>
                <div class="multi-choice-options">
                    ${optionsHTML}
                </div>
            </div>
        `;
    }

    generateFeaturesContent(step) {
        // Generate personalized features based on user profile
        const features = this.getPersonalizedFeatures();
        
        const featuresHTML = features.map(feature => `
            <div class="feature-card">
                <div class="feature-icon">
                    <i class="${feature.icon}"></i>
                </div>
                <div class="feature-content">
                    <h4>${feature.title}</h4>
                    <p>${feature.description}</p>
                </div>
            </div>
        `).join('');

        return `
            <div class="features-step">
                <h2 class="step-title">${step.title}</h2>
                <p class="step-subtitle">${step.subtitle}</p>
                <div class="features-grid">
                    ${featuresHTML}
                </div>
                <div class="personalization-note">
                    <i class="fas fa-magic"></i>
                    <span>Your experience has been personalized based on your preferences!</span>
                </div>
            </div>
        `;
    }

    getPersonalizedFeatures() {
        const features = [];
        
        // Add features based on user profile
        if (this.userProfile.experience === 'beginner') {
            features.push({
                icon: 'fas fa-graduation-cap',
                title: 'Learning Path',
                description: 'Structured learning path designed for beginners'
            });
        }
        
        if (this.userProfile.interests.includes('penetration-testing')) {
            features.push({
                icon: 'fas fa-bug',
                title: 'Penetration Testing Labs',
                description: 'Hands-on labs for ethical hacking practice'
            });
        }
        
        if (this.userProfile.goals.includes('network')) {
            features.push({
                icon: 'fas fa-users',
                title: 'Community Forums',
                description: 'Connect with cybersecurity professionals'
            });
        }
        
        if (this.userProfile.preferredContent.includes('hands-on-labs')) {
            features.push({
                icon: 'fas fa-flask',
                title: 'Interactive Labs',
                description: 'Real-world scenarios to practice your skills'
            });
        }
        
        // Add default features
        features.push({
            icon: 'fas fa-robot',
            title: 'AI Assistant',
            description: 'Get instant help and guidance'
        });
        
        features.push({
            icon: 'fas fa-store',
            title: 'Premium Store',
            description: 'Access exclusive tools and resources'
        });
        
        return features.slice(0, 6); // Limit to 6 features
    }

    initializeStepInteractions(step) {
        switch (step.type) {
            case 'choice':
                this.initializeChoiceInteractions();
                break;
            case 'multi-choice':
                this.initializeMultiChoiceInteractions(step);
                break;
        }
    }

    initializeChoiceInteractions() {
        const options = document.querySelectorAll('.choice-option');
        options.forEach(option => {
            option.addEventListener('click', () => {
                // Remove previous selection
                options.forEach(opt => opt.classList.remove('selected'));
                // Select current option
                option.classList.add('selected');
                
                // Store selection
                const step = this.steps[this.currentStep];
                this.userProfile[step.id] = option.dataset.value;
                
                // Enable next button
                document.getElementById('nextBtn').disabled = false;
            });
        });
    }

    initializeMultiChoiceInteractions(step) {
        const options = document.querySelectorAll('.multi-choice-option');
        const selectedOptions = [];
        
        options.forEach(option => {
            option.addEventListener('click', () => {
                const value = option.dataset.value;
                
                if (option.classList.contains('selected')) {
                    // Deselect
                    option.classList.remove('selected');
                    const index = selectedOptions.indexOf(value);
                    if (index > -1) selectedOptions.splice(index, 1);
                } else {
                    // Select (if under limit)
                    if (selectedOptions.length < step.maxSelections) {
                        option.classList.add('selected');
                        selectedOptions.push(value);
                    }
                }
                
                // Store selection
                this.userProfile[step.id] = [...selectedOptions];
                
                // Update next button state
                const nextBtn = document.getElementById('nextBtn');
                nextBtn.disabled = selectedOptions.length === 0;
            });
        });
    }

    updateProgress(stepIndex) {
        const progress = ((stepIndex + 1) / this.steps.length) * 100;
        const progressBar = document.getElementById('progressBar');
        const currentStepNumber = document.getElementById('currentStepNumber');
        const totalSteps = document.getElementById('totalSteps');
        
        progressBar.style.width = `${progress}%`;
        currentStepNumber.textContent = stepIndex + 1;
        totalSteps.textContent = this.steps.length;
    }

    updateNavigation(stepIndex) {
        const prevBtn = document.getElementById('prevBtn');
        const nextBtn = document.getElementById('nextBtn');
        
        // Show/hide previous button
        prevBtn.style.display = stepIndex === 0 ? 'none' : 'inline-block';
        
        // Update next button text
        if (stepIndex === this.steps.length - 1) {
            nextBtn.innerHTML = 'Get Started! <i class="fas fa-rocket"></i>';
            nextBtn.className = 'btn btn-success';
        } else {
            nextBtn.innerHTML = 'Continue <i class="fas fa-arrow-right"></i>';
            nextBtn.className = 'btn btn-primary';
        }
        
        // Disable next button initially for choice steps
        if (this.steps[stepIndex].type === 'choice' || this.steps[stepIndex].type === 'multi-choice') {
            nextBtn.disabled = true;
        }
    }

    nextStep() {
        if (this.currentStep < this.steps.length - 1) {
            this.currentStep++;
            this.loadStep(this.currentStep);
        } else {
        this.completeOnboarding();
        }
    }

    prevStep() {
        if (this.currentStep > 0) {
            this.currentStep--;
            this.loadStep(this.currentStep);
        }
    }

    skipOnboarding() {
        this.completeOnboarding();
    }

    completeOnboarding() {
        // Save user profile
        localStorage.setItem('pentrax_user_profile', JSON.stringify(this.userProfile));
        localStorage.setItem('pentrax_onboarding_completed', 'true');
        
        // Hide modal
        const modal = bootstrap.Modal.getInstance(document.getElementById('onboardingModal'));
        modal.hide();
        
        // Clean up
        setTimeout(() => {
            const modalEl = document.getElementById('onboardingModal');
            if (modalEl) modalEl.remove();
        }, 500);
        
        // Show welcome animation
        this.showWelcomeAnimation();
        // After welcome, offer guided tour
        setTimeout(() => {
            if (!localStorage.getItem('pentrax_guided_tour_completed')) {
                this.showTourPrompt();
            }
        }, 1200);
    }

    showTourPrompt() {
        // Modal HTML for tour prompt
        const promptHTML = `
            <div class="modal fade" id="tourPromptModal" tabindex="-1" data-bs-backdrop="static" data-bs-keyboard="false">
                <div class="modal-dialog modal-dialog-centered">
                    <div class="modal-content bg-dark text-white">
                        <div class="modal-header border-0">
                            <h5 class="modal-title"><i class="fas fa-map-signs me-2"></i>Quick Tour?</h5>
                        </div>
                        <div class="modal-body">
                            <p>Would you like a quick tour of PentraX's main features? You can exit at any time.</p>
                        </div>
                        <div class="modal-footer border-0">
                            <button class="btn btn-secondary" id="skipTourBtn">No, thanks</button>
                            <button class="btn btn-primary" id="startTourBtn">Yes, show me</button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        document.body.insertAdjacentHTML('beforeend', promptHTML);
        const modal = new bootstrap.Modal(document.getElementById('tourPromptModal'));
        modal.show();
        document.getElementById('skipTourBtn').onclick = () => {
            localStorage.setItem('pentrax_guided_tour_completed', 'skipped');
            modal.hide();
            setTimeout(() => {
                const el = document.getElementById('tourPromptModal');
                if (el) el.remove();
            }, 500);
        };
        document.getElementById('startTourBtn').onclick = () => {
            modal.hide();
            setTimeout(() => {
                const el = document.getElementById('tourPromptModal');
                if (el) el.remove();
                this.startGuidedTour();
            }, 500);
        };
    }

    startGuidedTour() {
        // Define the tour steps: selector, title, description
        this.tourSteps = [
            {
                selector: '.navbar-brand',
                title: 'Home',
                description: 'Return to the PentraX dashboard from anywhere.'
            },
            {
                selector: '.nav-link[href*="forums"], .nav-link.dropdown-toggle:has(i.fa-comments)',
                title: 'Forums',
                description: 'Join discussions, share tools, report bugs, and find jobs.'
            },
            {
                selector: '.nav-link[href*="cyber_labs"], .fa-flask',
                title: 'Cyber Labs',
                description: 'Practice your skills with hands-on cybersecurity labs.'
            },
            {
                selector: '.nav-link[href*="store"], .fa-store',
                title: 'Store',
                description: 'Browse and purchase premium tools, scripts, and resources.'
            },
            {
                selector: '.nav-link[href*="messages"], .fa-envelope',
                title: 'Messages',
                description: 'Check your private messages and chat securely.'
            },
            {
                selector: '.dropdown-menu-end .dropdown-item[href*="profile"], .fa-user',
                title: 'Profile',
                description: 'View and edit your profile, settings, and purchases.'
            },
            {
                selector: '#ai-assistant, .ai-toggle',
                title: 'AI Assistant',
                description: 'Get instant help and guidance from the PentraX AI Assistant.'
            }
        ];
        this.currentTourStep = 0;
        this.showTourStep(this.currentTourStep);
    }

    showTourStep(stepIdx) {
        // Remove any existing tour overlays
        document.querySelectorAll('.pentrax-tour-overlay, .pentrax-tour-tooltip').forEach(el => el.remove());
        if (stepIdx >= this.tourSteps.length) {
            localStorage.setItem('pentrax_guided_tour_completed', 'true');
            return;
        }
        const step = this.tourSteps[stepIdx];
        const target = document.querySelector(step.selector);
        if (!target) {
            // If not found, skip to next
            this.showTourStep(stepIdx + 1);
            return;
        }
        // Highlight target
        const rect = target.getBoundingClientRect();
        // Overlay
        const overlay = document.createElement('div');
        overlay.className = 'pentrax-tour-overlay';
        overlay.style.position = 'fixed';
        overlay.style.top = '0';
        overlay.style.left = '0';
        overlay.style.width = '100vw';
        overlay.style.height = '100vh';
        overlay.style.background = 'rgba(0,0,0,0.5)';
        overlay.style.zIndex = '2000';
        overlay.onclick = () => {};
        document.body.appendChild(overlay);
        // Tooltip
        const tooltip = document.createElement('div');
        tooltip.className = 'pentrax-tour-tooltip card shadow-lg';
        tooltip.style.position = 'fixed';
        tooltip.style.zIndex = '2100';
        tooltip.style.maxWidth = '320px';
        tooltip.style.background = '#222';
        tooltip.style.color = '#fff';
        tooltip.style.borderRadius = '12px';
        tooltip.style.padding = '1.2rem';
        tooltip.style.boxShadow = '0 8px 32px rgba(0,0,0,0.25)';
        tooltip.innerHTML = `
            <div class="mb-2"><strong>${step.title}</strong></div>
            <div class="mb-3">${step.description}</div>
            <div class="d-flex justify-content-between">
                <button class="btn btn-outline-light btn-sm" id="exitTourBtn">Exit Tour</button>
                <button class="btn btn-primary btn-sm" id="nextTourBtn">Next</button>
            </div>
        `;
        // Position tooltip near target
        let top = rect.bottom + 12;
        let left = rect.left;
        if (top + 160 > window.innerHeight) top = rect.top - 180;
        if (left + 340 > window.innerWidth) left = window.innerWidth - 340;
        if (left < 10) left = 10;
        tooltip.style.top = `${top}px`;
        tooltip.style.left = `${left}px`;
        document.body.appendChild(tooltip);
        // Scroll into view if needed
        target.scrollIntoView({behavior: 'smooth', block: 'center'});
        // Button handlers
        tooltip.querySelector('#exitTourBtn').onclick = () => {
            document.querySelectorAll('.pentrax-tour-overlay, .pentrax-tour-tooltip').forEach(el => el.remove());
            localStorage.setItem('pentrax_guided_tour_completed', 'skipped');
        };
        tooltip.querySelector('#nextTourBtn').onclick = () => {
            this.showTourStep(stepIdx + 1);
        };
    }

    showWelcomeAnimation() {
        // Add welcome animation to main content
        const mainContent = document.querySelector('.container-fluid, .container, main');
        if (mainContent) {
            mainContent.classList.add('welcome-animation');
            setTimeout(() => {
                mainContent.classList.remove('welcome-animation');
            }, 1000);
        }

        // Show personalized welcome toast
        this.showWelcomeToast();
    }

    showWelcomeToast() {
        const experience = this.userProfile.experience || 'cybersecurity';
        const interests = this.userProfile.interests || [];
        const interestText = interests.length > 0 ? `, especially ${interests[0]}` : '';
        
        const toastHTML = `
            <div class="toast-container position-fixed top-0 end-0 p-3">
                <div id="welcomeToast" class="toast align-items-center text-white bg-success border-0" role="alert">
                    <div class="d-flex">
                        <div class="toast-body">
                            <i class="fas fa-rocket me-2"></i>
                            Welcome to PentraX! Your ${experience} journey${interestText} starts now.
                        </div>
                        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
                    </div>
                </div>
            </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', toastHTML);
        const toast = new bootstrap.Toast(document.getElementById('welcomeToast'));
        toast.show();
        
        // Clean up toast after it's hidden
        setTimeout(() => {
            const toastEl = document.getElementById('welcomeToast');
            if (toastEl) toastEl.parentElement.remove();
        }, 5000);
    }
}

// Export for global access
window.OnboardingManager = OnboardingManager;