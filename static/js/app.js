document.addEventListener('DOMContentLoaded', () => {
    const state = {
        annotatorId: null,
        caseId: null,
        modelA: null,
        modelB: null,
        choices: {
            coherence: null,
            adherence: null,
            clarity: null,
            empathy: null
        }
    };

    // DOM Elements
    const elements = {
        annotatorDisplay: document.getElementById('annotator-id-display'),
        progressDisplay: document.getElementById('progress-display'),
        caseCategory: document.getElementById('case-category'),
        diseaseChoices: document.getElementById('disease-choices'),
        modelAName: document.getElementById('model-a-name'),
        modelADialogue: document.getElementById('model-a-dialogue'),
        modelBName: document.getElementById('model-b-name'),
        modelBDialogue: document.getElementById('model-b-dialogue'),
        loadingMessage: document.getElementById('loading-message'),
        completionMessage: document.getElementById('completion-message'),
        comparisonView: document.getElementById('comparison-view'),
        controlsView: document.getElementById('controls-view'),
        submitAllBtn: document.getElementById('submit-all-btn'),
        choiceButtons: document.querySelectorAll('.choice-btn')
        
    };

    const getAnnotatorId = () => {
        const urlParams = new URLSearchParams(window.location.search);
        let id = urlParams.get('annotator_id');
        if (!id) {
            id = prompt("请输入您的标注员ID (例如: doctor_wang):");
            if (!id) {
                alert("必须提供标注员ID才能开始！");
                return null;
            }
            // 更新URL并刷新，以便ID保留
            window.location.search = `?annotator_id=${id}`;
        }
        return id;
    };

    const displayCompletionScreen = () => {
        // 隐藏主应用容器
        const mainContainer = document.querySelector('.container');
        if (mainContainer) {
            mainContainer.style.display = 'none';
        }
        
        // 显示全屏的完成遮罩层
        const overlay = document.getElementById('completion-overlay');
        if (overlay) {
            overlay.style.display = 'flex'; // 使用flex来居中内容
        }
    };

    const resetForNextPair = () => {
        // Reset choices state
        for (const key in state.choices) {
            state.choices[key] = null;
        }
        // Reset button styles
        elements.choiceButtons.forEach(btn => btn.classList.remove('selected'));
        // Disable submit button
        elements.submitAllBtn.disabled = true;
    };

    const fetchNextPair = async () => {
        showLoading(true);
        resetForNextPair();
        try {
            const response = await fetch(`/get_comparison_pair?annotator_id=${state.annotatorId}`);
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            const data = await response.json();
            if (data.progress_total) {
                elements.progressDisplay.textContent = `${data.progress_completed} / ${data.progress_total}`;
           }

            if (data.message) {
                displayCompletionScreen(); 
                return;
            }
            if (data.error) {
                alert(`错误: ${data.error}`);
                return;
            }

            // 更新状态
            state.caseId = data.case_id;
            state.modelA = data.model_a_info.name;
            state.modelB = data.model_b_info.name;

            elements.caseCategory.textContent = data.category || 'N/A';
            // elements.diseaseChoices.textContent = data.choices || 'N/A';
            const choicesData = data.choices;
            let choicesArray = [];
            if (typeof choicesData === 'string' && choicesData.trim() !== '') {
                choicesArray = choicesData.split(',').map(choice => choice.trim());
            } 
            // Case 2: The data is already an array with content.
            else if (Array.isArray(choicesData) && choicesData.length > 0) {
                choicesArray = choicesData; // Use the array directly
            }

            // Now, if we have a valid array, format it for display.
            if (choicesArray.length > 0) {
                const formattedChoices = choicesArray
                    .map((name, index) => `(${index + 1}) ${name}`)
                    .join(', ');
                elements.diseaseChoices.textContent = formattedChoices;
            } else {
                // This will handle null, undefined, empty string, or empty array cases.
                elements.diseaseChoices.textContent = 'N/A';
            }

            // 更新UI
            elements.modelAName.textContent = `模型 A`;
            // elements.modelAName.textContent = `模型 A (${state.modelA})`;
            // elements.modelADialogue.textContent = data.model_a_info.dialogue;
            elements.modelADialogue.innerHTML = data.model_a_info.dialogue;
            elements.modelBName.textContent = `模型 B`;
            // elements.modelBName.textContent = `模型 B (${state.modelB})`;
            // elements.modelBDialogue.textContent = data.model_b_info.dialogue;
            elements.modelBDialogue.innerHTML = data.model_b_info.dialogue;
            
        } catch (error) {
            console.error('Failed to fetch comparison pair:', error);
            // alert('加载下一组对话失败，请检查后端服务是否开启。');
        } finally {
            showLoading(false);
        }
    };

    // --- NEW: Logic to handle clicks on any choice button ---
    const handleChoiceClick = (event) => {
        const clickedButton = event.target;
        const metricGroup = clickedButton.closest('.metric-group');
        const metric = metricGroup.dataset.metric;
        const choiceValue = clickedButton.dataset.choice;

        // Determine the actual winner name ('model_a' is a placeholder)
        let winnerName = choiceValue;
        if (choiceValue === 'model_a') winnerName = state.modelA;
        if (choiceValue === 'model_b') winnerName = state.modelB;
        
        state.choices[metric] = winnerName;

        // Update UI for this group
        metricGroup.querySelectorAll('.choice-btn').forEach(btn => {
            btn.classList.remove('selected');
        });
        clickedButton.classList.add('selected');

        checkAllMetricsSelected();
    };

    // --- NEW: Check if all metrics have been selected ---
    const checkAllMetricsSelected = () => {
        const allSelected = Object.values(state.choices).every(choice => choice !== null);
        elements.submitAllBtn.disabled = !allSelected;
    };

    const submitAnnotation = async (winner) => {
        const payload = {
            annotator_id: state.annotatorId,
            case_id: state.caseId,
            model_a: state.modelA,
            model_b: state.modelB,
            winners: state.choices
        };

        elements.submitAllBtn.disabled = true; // Prevent double clicks
        elements.submitAllBtn.textContent = '提交所有评测';

        try {
            const response = await fetch('/submit_annotation', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const result = await response.json();
            if (result.success) {
                fetchNextPair(); // 成功后加载下一组
            } else {
                throw new Error(result.error || 'Unknown error');
            }
        } catch (error) {
            console.error('Failed to submit annotation:', error);
            alert('提交标注失败，请稍后重试。');
            elements.submitAllBtn.disabled = false;
        }
    };

    const showLoading = (isLoading) => {
        elements.loadingMessage.style.display = isLoading ? 'block' : 'none';
        elements.comparisonView.style.display = isLoading ? 'none' : 'flex';
        elements.controlsView.style.display = isLoading ? 'none' : 'block';
    };
    
    const showCompletion = (message) => {
        elements.loadingMessage.style.display = 'none';
        elements.comparisonView.style.display = 'none';
        elements.controlsView.style.display = 'none';
        elements.completionMessage.textContent = message;
        elements.completionMessage.style.display = 'block';
    };

    // 初始化
    state.annotatorId = getAnnotatorId();
    if (state.annotatorId) {
        elements.annotatorDisplay.textContent = state.annotatorId;
        fetchNextPair();
    }

    // 绑定事件
    // elements.chooseABtn.addEventListener('click', () => submitAnnotation(state.modelA));
    // elements.chooseBBtn.addEventListener('click', () => submitAnnotation(state.modelB));
    // elements.chooseTieBtn.addEventListener('click', () => submitAnnotation('tie'));

    elements.choiceButtons.forEach(button => {
        button.addEventListener('click', handleChoiceClick);
    });
    elements.submitAllBtn.addEventListener('click', submitAnnotation);
});