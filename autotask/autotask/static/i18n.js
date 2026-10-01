(function () {
  'use strict';

  var translations = {
    '打开导航菜单': 'Open navigation menu', '主导航': 'Main navigation',
    '任务中心': 'Task Center', '新建任务': 'New Task', '设置': 'Settings', '退出': 'Log out',
    '切换为夜间模式': 'Switch to dark mode', '切换为日间模式': 'Switch to light mode',
    '关闭': 'Close', '取消': 'Cancel', '确认': 'Confirm',
    '提交失败，请检查网络后重试': 'Submission failed. Check your connection and try again.',
    '登录': 'Sign in', '密码': 'Password', '密码错误': 'Incorrect password',
    '配置文件:': 'Config file:', '脚本目录:': 'Scripts directory:',
    'Cron 时区:': 'Cron time zone:', '（跟随运行服务的系统时区）': '(Uses the service system time zone)',
    '修改密码': 'Change password', '留空则不修改': 'Leave blank to keep the current password',
    '保存': 'Save', '保存修改': 'Save changes', '创建任务': 'Create task',
    '任务中心 - AutoTask': 'Task Center - AutoTask', '登录 - AutoTask': 'Sign in - AutoTask',
    '设置 - AutoTask': 'Settings - AutoTask',
    '返回任务中心': 'Back to Task Center', '返回运行记录': 'Back to Run History',
    '← 返回任务中心': '← Back to Task Center', '← 返回运行记录': '← Back to Run History',
    '编辑任务': 'Edit Task', '新建任务': 'New Task', '更新任务的脚本、说明和执行方式。': 'Update the task script, description, and execution settings.',
    '先选择任务类型，再填写脚本与执行计划。': 'Choose a task type, then enter the script and schedule.',
    '任务类型': 'Task Type', '重复任务会持续保留并按计划运行；一次性任务只会执行一遍。': 'Recurring tasks stay active and run on a schedule. One-off tasks run once.',
    '重复任务': 'Recurring Tasks', '一次性任务': 'One-off Tasks',
    'Cron、固定间隔、Webhook 或手动反复执行': 'Repeat on a Cron schedule, interval, webhook, or manually',
    '立即启动或在指定时间只执行一次': 'Run once now or at a scheduled time',
    '基本信息': 'Basic Information', '名称用于识别任务；说明会显示在任务中心。': 'The name identifies this task. Its description appears on the Task Center.',
    '任务名称': 'Task Name', '例如：每日天气推送': 'e.g. Daily weather update',
    '任务说明': 'Description', '简要说明它做什么、何时需要关注……': 'Briefly describe what it does and when it needs attention…',
    '可留空；最多 1000 个字符。': 'Optional; up to 1,000 characters.',
    '脚本文件': 'Script File', '-- 选择脚本 --': '-- Select a script --',
    'JSON 数组，例如 ["--foo", "bar"]': 'JSON array, e.g. ["--foo", "bar"]',
    '例如：*/5 * * * *': 'e.g. */5 * * * *',
    '重复任务脚本': 'Recurring Task Scripts', '一次性任务脚本': 'One-off Task Scripts',
    ' 下的脚本会自动列在这里。': ' Scripts in the folder above are listed here automatically.',
    '下的脚本会自动列在这里。': 'Scripts in the folder above are listed here automatically.',
    '命令行参数': 'Command-line Arguments', '可留空。参数会原样传给脚本。': 'Optional. Arguments are passed to the script as entered.',
    '调度方式': 'Schedule Type', '手动（不自动运行）': 'Manual (no automatic runs)',
    '固定间隔': 'Fixed Interval', 'Webhook（HTTP 触发）': 'Webhook (HTTP trigger)',
    '重复执行计划': 'Recurring Schedule', '选择任务自动触发的方式；手动和 Webhook 不需要填写调度值。': 'Choose how to trigger this task. Manual and webhook schedules need no schedule value.',
    '调度值': 'Schedule Value', '标准 5 段 Cron 表达式。': 'Standard five-field Cron expression.',
    'Webhook 模式无需填写': 'Not needed for webhook schedules',
    '收到合法的 HTTP Webhook 请求时运行。': 'Runs when a valid HTTP webhook request is received.',
    '手动模式无需填写': 'Not needed for manual schedules',
    '仅从任务中心或命令行手动启动。': 'Start manually from the Task Center or command line.',
    'Cron 使用 5 个字段：': 'Cron uses five fields:', '分钟、小时、日、月、星期；按系统时区': 'minute, hour, day, month, and weekday; interpreted in the system time zone',
    'Cron 常用示例': 'Common Cron examples', '每 5 分钟': 'Every 5 minutes', '每天 09:00': 'Daily at 09:00',
    '工作日 08:30': 'Weekdays at 08:30', '每月 1 日 00:00': 'At 00:00 on the first of each month',
    '任意值': 'any value', '多个值': 'multiple values', '范围': 'range', '步长': 'step',
    '启用调度': 'Enable schedule', '保存后按上方计划自动运行。': 'After saving, the task runs automatically on the schedule above.',
    '一次性执行计划': 'One-off Schedule', '一次性任务完成、失败或取消后不会再次自动运行。': 'A one-off task will not run automatically again after it completes, fails, or is cancelled.',
    '一次性执行方式': 'One-off Run Mode', '创建后立即执行': 'Run immediately after creation',
    '适合长时间运行的临时作业；保存后后台立即启动。': 'For temporary jobs that may run for a while; starts in the background after saving.',
    '指定时间执行': 'Run at a scheduled time', '到达计划时间后启动一次，保留运行记录。': 'Starts once at the scheduled time and keeps a run record.',
    '执行时间': 'Run Time', '按服务系统时区': 'Uses the service system time zone', '解析。请填写未来时间。': 'Please choose a future time.',
    'Cron 表达式': 'Cron Expression', '例如：3600': 'e.g. 3600', ' 选择脚本': ' Select a script',
    '运行记录': 'Run History', '运行日志': 'Run Log', '触发方式': 'Trigger', '开始时间': 'Started',
    '结束时间': 'Finished', '退出码': 'Exit Code', '操作': 'Actions', '查看日志': 'View Log',
    '暂无运行记录': 'No run history yet', '实时跟踪': 'Live', '运行中...': 'Running…',
    '开始:': 'Started:', '结束:': 'Finished:', '退出码:': 'Exit code:',
    '任务状态统计': 'Task status summary', '全部任务': 'All Tasks', '运行中': 'Running',
    '重复任务启用': 'Recurring Tasks Enabled', '最近失败': 'Recent Failures', '任务分组': 'Task Groups',
    '所有任务': 'All Tasks', '未分组': 'Unassigned', '新建分组': 'New Group', '+ 新建分组': '+ New Group',
    '双击重命名': 'Double-click to rename', '管理分组': 'Manage group',
    '移动到其他分组': 'Move to another group', '任务类型': 'Task Type',
    '适合按 Cron、固定间隔、Webhook 或手动反复执行的工作。': 'For work that runs repeatedly on a Cron schedule, interval, webhook, or manually.',
    '+ 新建重复任务': '+ New Recurring Task', '+ 新建一次性任务': '+ New One-off Task',
    '启用': 'Enable', '停用': 'Disable', '已启用': 'Enabled', '已停用': 'Disabled',
    'once_immediate': 'Immediate', 'once_scheduled': 'Scheduled',
    '停止': 'Stop', '立即运行': 'Run Now', '编辑': 'Edit', '删除': 'Delete',
    '调度': 'Schedule', '每': 'Every', '秒': 'seconds', 'Webhook 触发': 'Webhook trigger', '手动触发': 'Manual trigger',
    '最近一次': 'Last Run', '下次运行': 'Next Run', '异常': 'Error', '正常': 'OK', '失败': 'Failed', '暂无记录': 'No runs yet',
    '任务已开始运行': 'Task started', '一次性任务已开始运行': 'One-off task started',
    '已发送停止请求': 'Stop request sent', '任务状态已更新': 'Task status updated', '任务已删除': 'Task deleted',
    '确认删除任务': 'Delete task', '这不会删除脚本文件。': 'This will not delete the script file.',
    '确认取消一次性任务': 'Cancel one-off task', '这不会删除脚本文件。': 'This will not delete the script file.',
    '已完成': 'Completed', '已取消': 'Cancelled', '等待执行': 'Pending', '执行失败': 'Failed', '未知': 'Unknown',
    '执行方式': 'Run Mode', '定时执行一次': 'Run once at a scheduled time', '计划时间': 'Scheduled Time', '立即执行': 'Run Now', '再次执行': 'Run Again',
    '一次性任务已取消': 'One-off task cancelled', '还没有重复任务': 'No recurring tasks yet',
    '创建 Cron 或固定间隔任务，让日常工作自动完成。': 'Create a Cron or interval task to automate routine work.',
    '新建重复任务 →': 'Create a recurring task →', '适合临时脚本和需要长时间运行的作业；每个任务只会执行一次。': 'For temporary scripts and longer jobs; each task runs only once.',
    '还没有一次性任务': 'No one-off tasks yet', '可安排在指定时间执行，或立即启动一个长时间运行的临时作业。': 'Schedule a task for later or start a temporary job now.',
    '新建一次性任务 →': 'Create a one-off task →', '参数': 'Args', '完成': 'Done', '重命名': 'Rename',
    '删除分组': 'Delete group', '移动到分组': 'Move to group', '最近一次运行失败': 'Most recent run failed',
    '新分组名称': 'New group name', '分组名称': 'Group name', '操作失败，请稍后重试': 'Action failed. Please try again later.',
    '操作未完成，请稍后重试': 'Action could not be completed. Please try again later.', '操作已完成': 'Action completed',
    '无法更新任务状态': 'Could not refresh task status', '分组已重命名': 'Group renamed', '分组无效': 'Invalid group',
    '密码至少 4 位': 'Password must be at least 4 characters', '密码已更新': 'Password updated',
    '任务名称不能为空，且不能含有路径分隔符': 'Task name is required and cannot contain path separators',
    '参数必须是 JSON 数组': 'Arguments must be a JSON array', '参数 JSON 数组中的每一项都必须是字符串': 'Every item in the arguments JSON array must be a string',
    '执行时间格式无效，请选择一个未来的本地时间': 'Invalid run time. Choose a future local time.',
    '一次性执行时间必须晚于当前时间': 'The one-off run time must be in the future.',
    '任务说明不能超过 1000 个字符': 'The description cannot exceed 1,000 characters', '无效的任务类型': 'Invalid task type',
    '任务类型创建后不能修改；请新建另一类任务': 'A task type cannot be changed after creation. Create a new task of the other type.',
    '任务名称同时决定脚本目录，创建后不能修改': 'The task name also determines its script folder and cannot be changed after creation.',
    '名称和脚本不能为空': 'Task name and script are required', '无效的调度方式': 'Invalid schedule type',
    '固定间隔必须是大于 0 的秒数': 'The interval must be a number of seconds greater than 0', 'Cron 表达式无效': 'Invalid Cron expression',
    '无效的一次性执行方式': 'Invalid one-off run mode', '一次性任务未能启动': 'Could not start the one-off task',
    '任务名已存在': 'A task with this name already exists', '请先停止运行中的任务，再删除': 'Stop the running task before deleting it',
    '任务正在运行中': 'The task is currently running', '一次性任务状态已变化，请刷新后重试': 'The one-off task status changed. Refresh and try again.',
    '一次性任务已被执行、取消或正在启动': 'The one-off task has already run, was cancelled, or is starting.',
    '任务当前未在运行': 'The task is not currently running', '只有一次性任务可以取消': 'Only one-off tasks can be cancelled',
    '任务不是可取消的等待状态': 'The task is not pending and cannot be cancelled', '日志文件不存在（可能已被清理）': 'Log file not found (it may have been cleaned up)',
    '重复任务已创建': 'Recurring task created', '任务已更新': 'Task updated',
    '任务不是可取消的等待状态': 'The task is not pending and cannot be cancelled',
    '单位为秒，例如 3600 表示每小时一次。': 'In seconds; for example, 3600 means once per hour.',
    '计算。': ' is used.'
  };

  var textNodes = new WeakMap();
  var attributes = new WeakMap();
  var currentLanguage = 'zh';
  var attributeNames = ['aria-label', 'aria-description', 'title', 'placeholder', 'label', 'data-label', 'data-confirm', 'data-success-message', 'data-empty-title', 'data-group-name'];

  function translate(value) {
    if (Object.prototype.hasOwnProperty.call(translations, value)) return translations[value];
    var match = value.match(/^参数 · (\d+)$/);
    if (match) return 'Args · ' + match[1];
    match = value.match(/^参数必须是 JSON 数组: (.+)$/);
    if (match) return 'Arguments must be a JSON array: ' + match[1];
    match = value.match(/^(.+) 下的脚本会自动列在这里。$/);
    if (match) return 'Scripts in ' + match[1] + ' are listed here automatically.';
    match = value.match(/^脚本必须位于 scripts\/(once|cron)\/(.+) 中$/);
    if (match) return 'The script must be inside scripts/' + match[1] + '/' + match[2] + '/';
    match = value.match(/^(cron|interval) 任务需要填写调度值$/);
    if (match) return (match[1] === 'cron' ? 'Cron' : 'Interval') + ' tasks need a schedule value.';
    match = value.match(/^一次性任务当前为“(.+)”，不能再编辑$/);
    if (match) return 'This one-off task is ' + translate(match[1]) + ' and can no longer be edited.';
    match = value.match(/^每 (.+) 秒$/);
    if (match) return 'Every ' + match[1] + ' seconds';
    match = value.match(/^(.+) 运行日志 - AutoTask$/);
    if (match) return match[1] + ' Run Log - AutoTask';
    match = value.match(/^运行日志 #(\d+) - AutoTask$/);
    if (match) return 'Run Log #' + match[1] + ' - AutoTask';
    match = value.match(/^(编辑任务|新建任务) - AutoTask$/);
    if (match) return (match[1] === '编辑任务' ? 'Edit Task' : 'New Task') + ' - AutoTask';
    match = value.match(/^管理分组「(.+)」$/);
    if (match) return 'Manage group “' + match[1] + '”';
    match = value.match(/^删除分组「(.+)」？(?:其中的 (\d+) 个任务会移到未分组，任务本身不受影响。)?$/);
    if (match) return 'Delete group “' + match[1] + '”?' + (match[2] ? ' Its ' + match[2] + ' task(s) will move to Unassigned.' : '');
    match = value.match(/^确认删除任务「(.+)」？这不会删除脚本文件。$/);
    if (match) return 'Delete task “' + match[1] + '”? This will not delete the script file.';
    match = value.match(/^确认取消一次性任务「(.+)」？$/);
    if (match) return 'Cancel one-off task “' + match[1] + '”?';
    match = value.match(/^任务 (.+) 已删除$/);
    if (match) return 'Task ' + match[1] + ' deleted';
    match = value.match(/^任务 (.+) 已触发运行$/);
    if (match) return 'Task ' + match[1] + ' was started';
    match = value.match(/^任务 (.+) 失败（进程可能已结束）$/);
    if (match) return 'Could not stop task ' + match[1] + ' (the process may have ended)';
    match = value.match(/^已发送停止信号给任务 (.+)$/);
    if (match) return 'Stop signal sent to task ' + match[1];
    match = value.match(/^分组已删除，(\d+) 个任务移至未分组$/);
    if (match) return 'Group deleted. ' + match[1] + ' task(s) moved to Unassigned.';
    match = value.match(/^已新建分组「(.+)」$/);
    if (match) return 'Group “' + match[1] + '” created';
    match = value.match(/^已移至(.+)$/);
    if (match) return 'Moved to ' + match[1];
    match = value.match(/^任务已移至(.+)$/);
    if (match) return 'Task moved to ' + match[1];
    match = value.match(/^任务已(启用|停用)$/);
    if (match) return 'Task ' + (match[1] === '启用' ? 'enabled' : 'disabled');
    match = value.match(/^一次性任务 (.+) 已取消$/);
    if (match) return 'One-off task ' + match[1] + ' cancelled';
    match = value.match(/^一次性任务已创建并在后台启动(?:（运行 #(\d+)）)?$/);
    if (match) return 'One-off task created and started in the background' + (match[1] ? ' (run #' + match[1] + ')' : '');
    match = value.match(/^任务已更新并在后台启动(?:（运行 #(\d+)）)?$/);
    if (match) return 'Task updated and started in the background' + (match[1] ? ' (run #' + match[1] + ')' : '');
    match = value.match(/^一次性任务已创建，将在 (.+) 执行$/);
    if (match) return 'One-off task created. It will run at ' + match[1];
    match = value.match(/^一次性任务 (.+) (已再次在后台启动|已在后台启动)$/);
    if (match) return 'One-off task ' + match[1] + (match[2] === '已再次在后台启动' ? ' restarted' : ' started in the background');
    match = value.match(/^一次性任务请使用“取消”而非启用\/停用$/);
    if (match) return 'Use Cancel for one-off tasks; they cannot be enabled or disabled.';
    match = value.match(/^任务已发送到未分组$/);
    if (match) return 'Task moved to Unassigned';
    return value;
  }

  function isUserContent(node) {
    var parent = node.parentElement;
    return !!(parent && parent.closest('.task-name-cell strong, .task-description, .group-chip-name, .script-scroll-text, .mono code, pre.log, option, input, textarea'));
  }

  function updateText(node) {
    if (!node || !node.parentElement || node.parentElement.closest('script, style, noscript')) return;
    var raw = node.nodeValue;
    var source = textNodes.get(node);
    if (source === undefined || (raw !== source && raw !== translate(source))) {
      source = raw;
      textNodes.set(node, source);
    }
    if (isUserContent(node)) return;
    var leading = (source.match(/^\s*/) || [''])[0];
    var trailing = (source.match(/\s*$/) || [''])[0];
    var content = source.slice(leading.length, source.length - trailing.length || undefined);
    if (!content) return;
    var output = leading + (currentLanguage === 'en' ? translate(content) : content) + trailing;
    if (node.nodeValue !== output) node.nodeValue = output;
  }

  function updateAttribute(element, name) {
    var raw = element.getAttribute(name);
    if (raw === null) return;
    var map = attributes.get(element);
    if (!map) { map = Object.create(null); attributes.set(element, map); }
    var source = map[name];
    if (source === undefined || (raw !== source && raw !== translate(source))) {
      source = raw;
      map[name] = source;
    }
    var output = currentLanguage === 'en' && !(name === 'data-group-name' && source !== '未分组') ? translate(source) : source;
    if (raw !== output) element.setAttribute(name, output);
  }

  function walk(root) {
    if (!root) return;
    if (root.nodeType === Node.TEXT_NODE) { updateText(root); return; }
    if (root.nodeType === Node.ELEMENT_NODE) attributeNames.forEach(function (name) { updateAttribute(root, name); });
    var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    var node;
    while ((node = walker.nextNode())) updateText(node);
    if (root.querySelectorAll) root.querySelectorAll('*').forEach(function (element) {
      attributeNames.forEach(function (name) { updateAttribute(element, name); });
    });
  }

  function setLanguage(language) {
    currentLanguage = language === 'en' ? 'en' : 'zh';
    document.documentElement.lang = currentLanguage === 'en' ? 'en' : 'zh-CN';
    document.documentElement.dataset.language = currentLanguage;
    try { localStorage.setItem('autotask:language', currentLanguage); } catch (ignore) {}
    var label = document.querySelector('[data-language-label]');
    var button = document.querySelector('[data-language-toggle]');
    if (label) label.textContent = currentLanguage === 'en' ? '中文' : 'English';
    if (button) button.setAttribute('aria-label', currentLanguage === 'en' ? 'Switch language to Chinese' : '切换为英文');
    walk(document.documentElement);
    window.dispatchEvent(new CustomEvent('autotask:languagechange', { detail: { language: currentLanguage } }));
  }

  window.AutoTaskI18n = {
    t: function (value) { return currentLanguage === 'en' ? translate(String(value)) : String(value); },
    language: function () { return currentLanguage; },
    setLanguage: setLanguage
  };
  document.addEventListener('click', function (event) {
    var button = event.target.closest('[data-language-toggle]');
    if (button) setLanguage(currentLanguage === 'en' ? 'zh' : 'en');
  });

  var observer = new MutationObserver(function (records) {
    records.forEach(function (record) {
      if (record.type === 'characterData') updateText(record.target);
      else if (record.type === 'attributes') updateAttribute(record.target, record.attributeName);
      else record.addedNodes.forEach(function (node) { walk(node); });
    });
  });
  observer.observe(document.documentElement, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: attributeNames });

  var savedLanguage = 'zh';
  try { savedLanguage = localStorage.getItem('autotask:language') || 'zh'; } catch (ignore) {}
  setLanguage(savedLanguage);
})();
