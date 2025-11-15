// 模型配置管理器
console.log('模型配置管理器开始加载');

// 全局变量
let globalModelConfigs = null;
const MODELS_CONFIG_PATH = '/static/models.json';
// 模型配置管理器
console.log('模型配置管理器开始加载');


// 获取默认模型配置
function getDefaultModelConfigs() {
    return {
        version: "1.4.1",
        models: {
            "kourichat-global": [
                {id: "gemini-2.5-flash", name: "gemini-2.5-flash"},
                {id: "gemini-2.5-pro", name: "gemini-2.5-pro"},
                {id: "kourichat-v3", name: "kourichat-v3"},
                {id: "gpt-4o", name: "gpt-4o"},
                {id: "grok-3", name: "grok-3"}
            ],
            "siliconflow": [
                {id: "deepseek-ai/DeepSeek-V3", name: "deepseek-ai/DeepSeek-V3"},
                {id: "deepseek-ai/DeepSeek-R1", name: "deepseek-ai/DeepSeek-R1"}
            ],
            "deepseek": [
                {id: "deepseek-chat", name: "deepseek-chat"},
                {id: "deepseek-reasoner", name: "deepseek-reasoner"}
            ]
        },
        vision_api_providers: [
            {
                id: "kourichat-global",
                name: "KouriChat API (推荐)",
                url: "https://api.kourichat.com/v1",
                register_url: "https://api.kourichat.com/register"
            },
            {
                id: "moonshot",
                name: "Moonshot AI",
                url: "https://api.moonshot.cn/v1",
                register_url: "https://platform.moonshot.cn/console/api-keys"
            },
            {
                id: "openai",
                name: "OpenAI",
                url: "https://api.openai.com/v1",
                register_url: "https://platform.openai.com/api-keys"
            }
        ],
        vision_models: {
            "kourichat-global": [
                {id: "kourichat-vision", name: "KouriChat Vision (推荐)"},
                {id: "gemini-2.5-pro", name: "Gemini 2.5 Pro"},
                {id: "gpt-4o", name: "GPT-4o"}
            ],
            "moonshot": [
                {id: "moonshot-v1-8k-vision-preview", name: "Moonshot V1 8K Vision (推荐)"},
                {id: "moonshot-v1-32k-vision", name: "Moonshot V1 32K Vision"}
            ],
            "openai": [
                {id: "gpt-4o", name: "GPT-4o (推荐)"},
                {id: "gpt-4-vision-preview", name: "GPT-4 Vision"}
            ]
        }
    };
}

// 从本地获取模型配置
async function fetchModelConfigs() {
    if (globalModelConfigs) {
        console.log('使用缓存的模型配置');
        return globalModelConfigs;
    }
    
    try {
        console.log('正在从本地获取模型配置...', MODELS_CONFIG_PATH);
        const response = await fetch(MODELS_CONFIG_PATH, {
            cache: 'no-cache'
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        
        // 验证配置结构
        if (!data.models && !data.vision_models) {
            throw new Error('模型配置结构不正确，缺少必要字段');
        }
        
        globalModelConfigs = data;
        console.log('✅ 本地模型配置获取成功，包含', Object.keys(data).join(', '));
        return globalModelConfigs;
        
    } catch (error) {
        console.warn('❌ 本地配置获取失败，使用默认配置:', error);
        
        // 使用默认配置作为回退
        globalModelConfigs = getDefaultModelConfigs();
        console.log('🔄 已设置默认配置作为回退');
        return globalModelConfigs;
    }
}

// 初始化模型选择框
async function initializeModelSelect(passedProviderId) {
    console.log("调用initializeModelSelect，提供商:", passedProviderId);
    
    const modelSelect = document.getElementById('model_select');
    const modelInput = document.getElementById('MODEL');
    const customModelInput = document.getElementById('customModelInput');
    
    // 检查必要元素
    if (!modelSelect) {
        console.error("初始化失败：模型选择器未找到");
        return;
    }
    
    if (!modelInput) {
        console.error("初始化失败：MODEL输入框未找到");
        return;
    }
    
    // 获取保存的模型值
    const savedModel = modelInput.value || '';
    
    // 获取当前选择的API提供商
    const apiSelect = document.getElementById('api_provider_select');
    const providerId = passedProviderId || (apiSelect ? apiSelect.value : 'kourichat-global');
    
    console.log("初始化模型选择器，当前提供商:", providerId, "保存的模型:", savedModel);
    
    // 清空选择框
    modelSelect.innerHTML = '';
    
    try {
        // 获取模型配置
        const configs = await fetchModelConfigs();
        
        // 根据提供商添加相应的模型选项
        if (configs && configs.models && configs.models[providerId]) {
            console.log(`为提供商 ${providerId} 加载 ${configs.models[providerId].length} 个模型`);
            configs.models[providerId].forEach(model => {
                const option = document.createElement('option');
                option.value = model.id;
                option.textContent = model.name || model.id;
                modelSelect.appendChild(option);
            });
        } else {
            console.warn(`提供商 ${providerId} 没有可用的模型配置`);
            throw new Error(`没有找到提供商 ${providerId} 的模型配置`);
        }
    } catch (error) {
        console.error("获取模型配置失败:", error);
        // 添加基本的回退选项
        const fallbackOptions = [
            {id: 'gpt-4o', name: 'GPT-4o'},
            {id: 'claude-3-5-sonnet', name: 'Claude 3.5 Sonnet'},
            {id: 'gemini-2.5-pro', name: 'Gemini 2.5 Pro'}
        ];
        console.log('使用回退选项:', fallbackOptions.length, '个模型');
        fallbackOptions.forEach(model => {
            const option = document.createElement('option');
            option.value = model.id;
            option.textContent = model.name;
            modelSelect.appendChild(option);
        });
    }
    
    // 确保自定义选项存在
    if (!modelSelect.querySelector('option[value="custom"]')) {
        modelSelect.innerHTML += '<option value="custom">自定义模型</option>';
    }
    
    // 处理不同情况
    if (providerId === 'ollama' || providerId === 'custom') {
        // 1. 自定义或Ollama提供商
        console.log("使用自定义/Ollama提供商");
        modelSelect.value = 'custom';
        
        // 显示自定义输入框
        if (customModelInput) {
            customModelInput.style.display = 'block';
            const inputField = customModelInput.querySelector('input');
            
            // 如果有保存的值，填充输入框
            if (inputField && savedModel) {
                inputField.value = savedModel;
            } else if (inputField) {
                inputField.value = '';
            }
        }
    } else if (savedModel) {
        // 2. 有保存的模型值
        // 检查保存的值是否在选项列表中
        const modelExists = Array.from(modelSelect.options).some(opt => opt.value === savedModel);
        
        if (modelExists) {
            // 如果在列表中，直接选择
            console.log("选择已保存的模型:", savedModel);
            modelSelect.value = savedModel;
            
            // 确保自定义输入框隐藏
            if (customModelInput) {
                customModelInput.style.display = 'none';
            }
        } else {
            // 如果不在列表中，视为自定义模型
            console.log("使用自定义模型:", savedModel);
            modelSelect.value = 'custom';
            
            // 显示并填充自定义输入框
            if (customModelInput) {
                customModelInput.style.display = 'block';
                const inputField = customModelInput.querySelector('input');
                if (inputField) {
                    inputField.value = savedModel;
                }
            }
        }
    } else {
        // 3. 没有保存的模型值，使用默认值
        console.log("无保存的模型值，使用默认值");
        if (modelSelect.options.length > 0) {
            modelSelect.selectedIndex = 0;
            modelInput.value = modelSelect.value;
            
            // 隐藏自定义输入框
            if (customModelInput) {
                customModelInput.style.display = 'none';
            }
        }
    }
}

// 更新图像识别模型选择框
async function updateVisionModelSelect(providerId) {
    console.log('更新图像识别模型选择器，提供商:', providerId);
    
    const modelSelect = document.getElementById('vision_model_select');
    const modelInput = document.getElementById('VISION_MODEL');
    const customModelInput = document.getElementById('customVisionModelInput');
    
    if (!modelSelect || !modelInput) {
        console.error('图像识别模型选择器或输入框未找到');
        return;
    }
    
    // 保存当前模型值
    const currentModelValue = modelInput.value;
    console.log('当前图像识别模型值:', currentModelValue);
    
    // 重置选择框
    modelSelect.innerHTML = '';
    
    if (providerId === 'custom') {
        modelSelect.innerHTML += '<option value="custom">自定义模型</option>';
        modelSelect.value = 'custom';
        
        // 显示自定义输入框并设置当前值
        if (customModelInput) {
            customModelInput.style.display = 'block';
            const inputField = customModelInput.querySelector('input');
            if (inputField) {
                inputField.value = currentModelValue || '';
            }
        }
        return;
    }
    
    if (!providerId) {
        console.warn('图像识别提供商ID为空');
        return;
    }
    
    try {
        // 获取配置
        const configs = await fetchModelConfigs();
        
        let models = [];
        
        // 获取识图模型配置
        if (configs && configs.vision_models && configs.vision_models[providerId]) {
            models = configs.vision_models[providerId];
            console.log(`为识图提供商 ${providerId} 加载 ${models.length} 个模型`);
        } else {
            console.warn(`识图提供商 ${providerId} 没有可用的模型配置`);
        }
        
        // 添加模型选项
        if (models.length) {
            models.forEach(model => {
                const option = document.createElement('option');
                option.value = model.id;
                option.textContent = model.name || model.id;
                modelSelect.appendChild(option);
            });
        } else {
            throw new Error(`没有找到识图提供商 ${providerId} 的模型配置`);
        }
        
        // 添加自定义模型选项
        const customOption = document.createElement('option');
        customOption.value = 'custom';
        customOption.textContent = '自定义模型';
        modelSelect.appendChild(customOption);
        
    } catch (error) {
        console.error('获取识图模型配置失败:', error);
        // 添加基本的识图模型回退选项
        const fallbackVisionOptions = [
            {id: 'gpt-4o', name: 'GPT-4o Vision'},
            {id: 'claude-3-5-sonnet-20241022', name: 'Claude 3.5 Sonnet Vision'},
            {id: 'gemini-2.5-pro', name: 'Gemini 2.5 Pro Vision'},
            {id: 'kourichat-vision', name: 'KouriChat Vision'}
        ];
        console.log('使用识图模型回退选项:', fallbackVisionOptions.length, '个模型');
        fallbackVisionOptions.forEach(model => {
            const option = document.createElement('option');
            option.value = model.id;
            option.textContent = model.name;
            modelSelect.appendChild(option);
        });
        
        // 添加自定义选项
        const customOption = document.createElement('option');
        customOption.value = 'custom';
        customOption.textContent = '自定义模型';
        modelSelect.appendChild(customOption);
    }
    
    // 恢复选择状态
    const modelExists = Array.from(modelSelect.options).some(opt => opt.value === currentModelValue);
    
    if (modelExists && currentModelValue !== 'custom') {
        // 如果当前值是预设模型之一
        console.log('选择预设图像识别模型:', currentModelValue);
        modelSelect.value = currentModelValue;
        if (customModelInput) customModelInput.style.display = 'none';
    } else if (currentModelValue) {
        // 如果当前值不在预设列表中且不为空，视为自定义模型
        console.log('使用自定义图像识别模型:', currentModelValue);
        modelSelect.value = 'custom';
        
        // 显示自定义输入框并设置值
        if (customModelInput) {
            customModelInput.style.display = 'block';
            const inputField = customModelInput.querySelector('input');
            if (inputField) {
                inputField.value = currentModelValue;
            }
        }
        
        // 确保隐藏输入框的值是自定义的值
        modelInput.value = currentModelValue;
    } else if (modelSelect.options.length > 1) {
        // 如果没有当前模型值，选择第一个有效选项（非自定义）
        console.log('选择默认图像识别模型');
        modelSelect.selectedIndex = 0;
        
        // 更新隐藏的值
        const selectedModel = modelSelect.value;
        if (selectedModel !== 'custom') {
            modelInput.value = selectedModel;
        }
        
        // 确保自定义输入框隐藏
        if (customModelInput) customModelInput.style.display = 'none';
    }
    
    console.log('图像识别模型选择器更新完成，当前选择:', modelSelect.value);
}

// 初始化意图识别模型选择框
async function initializeIntentModelSelect(passedProviderId) {
    console.log("调用initializeIntentModelSelect，提供商:", passedProviderId);
    
    const modelSelect = document.getElementById('intent_model_select');
    const modelInput = document.getElementById('INTENT_MODEL');
    const customModelInput = document.getElementById('intentCustomModelInput');
    
    // 检查必要元素
    if (!modelSelect) {
        console.error("初始化失败：意图识别模型选择器未找到");
        return;
    }
    
    if (!modelInput) {
        console.error("初始化失败：INTENT_MODEL输入框未找到");
        return;
    }
    
    // 获取保存的模型值
    const savedModel = modelInput.value || '';
    
    // 获取当前选择的API提供商
    const apiSelect = document.getElementById('intent_api_provider_select');
    const providerId = passedProviderId || (apiSelect ? apiSelect.value : 'kourichat-global');
    
    console.log("初始化意图识别模型选择器，当前提供商:", providerId, "保存的模型:", savedModel);
    
    // 清空选择框
    modelSelect.innerHTML = '';
    
    try {
        // 获取模型配置
        const configs = await fetchModelConfigs();
        
        // 根据提供商添加相应的模型选项
        if (configs && configs.models && configs.models[providerId]) {
            console.log(`为意图识别提供商 ${providerId} 加载 ${configs.models[providerId].length} 个模型`);
            configs.models[providerId].forEach(model => {
                const option = document.createElement('option');
                option.value = model.id;
                option.textContent = model.name || model.id;
                modelSelect.appendChild(option);
            });
        } else {
            console.warn(`意图识别提供商 ${providerId} 没有可用的模型配置`);
            throw new Error(`没有找到意图识别提供商 ${providerId} 的模型配置`);
        }
    } catch (error) {
        console.error("获取意图识别模型配置失败:", error);
        // 添加基本的回退选项
        const fallbackOptions = [
            {id: 'kourichat-v3', name: 'kourichat-v3'},
            {id: 'deepseek-ai/DeepSeek-V3', name: 'deepseek-ai/DeepSeek-V3'},
            {id: 'gpt-4o', name: 'GPT-4o'}
        ];
        console.log('使用意图识别回退选项:', fallbackOptions.length, '个模型');
        fallbackOptions.forEach(model => {
            const option = document.createElement('option');
            option.value = model.id;
            option.textContent = model.name;
            modelSelect.appendChild(option);
        });
    }
    
    // 确保自定义选项存在
    if (!modelSelect.querySelector('option[value="custom"]')) {
        modelSelect.innerHTML += '<option value="custom">自定义模型</option>';
    }
    
    // 处理不同情况
    if (providerId === 'ollama' || providerId === 'custom') {
        // 1. 自定义或Ollama提供商
        console.log("使用自定义/Ollama意图识别提供商");
        modelSelect.value = 'custom';
        
        // 显示自定义输入框
        if (customModelInput) {
            customModelInput.style.display = 'block';
            const inputField = customModelInput.querySelector('input');
            
            // 如果有保存的值，填充输入框
            if (inputField && savedModel) {
                inputField.value = savedModel;
            } else if (inputField) {
                inputField.value = '';
            }
        }
    } else if (savedModel) {
        // 2. 有保存的模型值
        // 检查保存的值是否在选项列表中
        const modelExists = Array.from(modelSelect.options).some(opt => opt.value === savedModel);
        
        if (modelExists) {
            // 如果在列表中，直接选择
            console.log("选择已保存的意图识别模型:", savedModel);
            modelSelect.value = savedModel;
            
            // 确保自定义输入框隐藏
            if (customModelInput) {
                customModelInput.style.display = 'none';
            }
        } else {
            // 如果不在列表中，视为自定义模型
            console.log("使用自定义意图识别模型:", savedModel);
            modelSelect.value = 'custom';
            
            // 显示并填充自定义输入框
            if (customModelInput) {
                customModelInput.style.display = 'block';
                const inputField = customModelInput.querySelector('input');
                if (inputField) {
                    inputField.value = savedModel;
                }
            }
        }
    } else {
        // 3. 没有保存的模型值，使用默认值
        console.log("无保存的意图识别模型值，使用默认值");
        if (modelSelect.options.length > 0) {
            modelSelect.selectedIndex = 0;
            modelInput.value = modelSelect.value;
            
            // 隐藏自定义输入框
            if (customModelInput) {
                customModelInput.style.display = 'none';
            }
        }
    }
}

// 更新意图识别模型选择框
async function updateIntentModelSelect(providerId) {
    console.log('更新意图识别模型选择器，提供商:', providerId);
    
    const modelSelect = document.getElementById('intent_model_select');
    const modelInput = document.getElementById('INTENT_MODEL');
    const customModelInput = document.getElementById('intentCustomModelInput');
    
    if (!modelSelect || !modelInput) {
        console.error('意图识别模型选择器或输入框未找到');
        return;
    }
    
    // 保存当前模型值
    const currentModelValue = modelInput.value;
    console.log('当前意图识别模型值:', currentModelValue);
    
    // 重置选择框
    modelSelect.innerHTML = '';
    
    if (providerId === 'custom') {
        modelSelect.innerHTML += '<option value="custom">自定义模型</option>';
        modelSelect.value = 'custom';
        
        // 显示自定义输入框并设置当前值
        if (customModelInput) {
            customModelInput.style.display = 'block';
            const inputField = customModelInput.querySelector('input');
            if (inputField) {
                inputField.value = currentModelValue || '';
            }
        }
        return;
    }
    
    if (!providerId) {
        console.warn('意图识别提供商ID为空');
        return;
    }
    
    try {
        // 获取配置
        const configs = await fetchModelConfigs();
        
        let models = [];
        
        // 获取模型配置
        if (configs && configs.models && configs.models[providerId]) {
            models = configs.models[providerId];
            console.log(`为意图识别提供商 ${providerId} 加载 ${models.length} 个模型`);
        } else {
            console.warn(`意图识别提供商 ${providerId} 没有可用的模型配置`);
        }
        
        // 添加模型选项
        if (models.length) {
            models.forEach(model => {
                const option = document.createElement('option');
                option.value = model.id;
                option.textContent = model.name || model.id;
                modelSelect.appendChild(option);
            });
        } else {
            throw new Error(`没有找到意图识别提供商 ${providerId} 的模型配置`);
        }
        
        // 添加自定义模型选项
        const customOption = document.createElement('option');
        customOption.value = 'custom';
        customOption.textContent = '自定义模型';
        modelSelect.appendChild(customOption);
        
    } catch (error) {
        console.error('获取意图识别模型配置失败:', error);
        // 添加基本的回退选项
        const fallbackOptions = [
            {id: 'kourichat-v3', name: 'kourichat-v3'},
            {id: 'deepseek-ai/DeepSeek-V3', name: 'deepseek-ai/DeepSeek-V3'},
            {id: 'gpt-4o', name: 'GPT-4o'}
        ];
        console.log('使用意图识别回退选项:', fallbackOptions.length, '个模型');
        fallbackOptions.forEach(model => {
            const option = document.createElement('option');
            option.value = model.id;
            option.textContent = model.name;
            modelSelect.appendChild(option);
        });
        
        // 添加自定义选项
        const customOption = document.createElement('option');
        customOption.value = 'custom';
        customOption.textContent = '自定义模型';
        modelSelect.appendChild(customOption);
    }
    
    // 恢复选择状态
    const modelExists = Array.from(modelSelect.options).some(opt => opt.value === currentModelValue);
    
    if (modelExists && currentModelValue !== 'custom') {
        // 如果当前值是预设模型之一
        console.log('选择预设意图识别模型:', currentModelValue);
        modelSelect.value = currentModelValue;
        if (customModelInput) customModelInput.style.display = 'none';
    } else if (currentModelValue) {
        // 如果当前值不在预设列表中且不为空，视为自定义模型
        console.log('使用自定义意图识别模型:', currentModelValue);
        modelSelect.value = 'custom';
        
        // 显示自定义输入框并设置值
        if (customModelInput) {
            customModelInput.style.display = 'block';
            const inputField = customModelInput.querySelector('input');
            if (inputField) {
                inputField.value = currentModelValue;
            }
        }
        
        // 确保隐藏输入框的值是自定义的值
        modelInput.value = currentModelValue;
    } else if (modelSelect.options.length > 1) {
        // 如果没有当前模型值，选择第一个有效选项（非自定义）
        console.log('选择默认意图识别模型');
        modelSelect.selectedIndex = 0;
        
        // 更新隐藏的值
        const selectedModel = modelSelect.value;
        if (selectedModel !== 'custom') {
            modelInput.value = selectedModel;
        }
        
        // 确保自定义输入框隐藏
        if (customModelInput) customModelInput.style.display = 'none';
    }
    
    console.log('意图识别模型选择器更新完成，当前选择:', modelSelect.value);
}

// 暴露全局函数
window.getModelConfigs = fetchModelConfigs;
window.initializeModelSelect = initializeModelSelect;
window.updateVisionModelSelect = updateVisionModelSelect;
window.initializeIntentModelSelect = initializeIntentModelSelect;
window.updateIntentModelSelect = updateIntentModelSelect;

// 页面加载时预先获取配置
document.addEventListener('DOMContentLoaded', function() {
    console.log('模型配置管理器初始化');
    // 预先获取配置，但不阻塞页面加载
    fetchModelConfigs().then(() => {
        console.log('模型配置预加载完成');
    }).catch(error => {
        console.warn('模型配置预加载失败:', error);
    });
});

console.log('模型配置管理器加载完成');