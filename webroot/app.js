'use strict';

var CONTROL = '/data/adb/modules/uid_path_filter_rules/control.sh';

/* ---------- exec bridge ---------- */

var cbSeq = 0;

function exec(cmd) {
    return new Promise(function (resolve) {
        if (!(window.ksu && typeof window.ksu.exec === 'function')) {
            resolve({ errno: 1, out: '', err: 'ksu is not defined' });
            return;
        }
        var name = 'upf_cb_' + (++cbSeq);
        window[name] = function (errno, stdout, stderr) {
            delete window[name];
            resolve({ errno: errno || 0, out: (stdout || '').trim(), err: (stderr || '').trim() });
        };
        window.ksu.exec(cmd, '{}', name);
    });
}

function run(args) { return exec('sh ' + CONTROL + ' ' + args); }

/* ---------- state ---------- */

var state = {
    targets: [], pkgs: [], apps: null,
    uidMap: {}, rules: [], labels: {},
    sysfs: '?', writable: '?', kernel: '', module: '',
    dirty: false, labelsLoaded: false
};

function $(id) { return document.getElementById(id); }

function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
        return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
}

function toast(msg, isErr) {
    var el = $('snackbar');
    if (window.ksu && typeof window.ksu.toast === 'function' && !isErr) {
        try { window.ksu.toast(msg); } catch (e) { /* fall through */ }
    }
    el.textContent = msg;
    el.classList.toggle('err', !!isErr);
    el.hidden = false;
    clearTimeout(toast._t);
    if (!isErr) toast._t = setTimeout(function () { el.hidden = true; }, 3500);
}

/* ---------- status parsing ---------- */

function parseStatus(out) {
    var st = {
        targets: [], pkgs: [], rules: [], uidMap: {},
        sysfs: '?', writable: '?', kernel: '', module: ''
    };
    var inRules = false;
    out.split('\n').forEach(function (line) {
        if (line === '---rules') { inRules = true; return; }
        if (line === '---end') { inRules = false; return; }
        if (inRules) { if (line) st.rules.push(line); return; }
        if (line.indexOf('module=') === 0)      st.module = line.slice(7);
        else if (line.indexOf('kernel=') === 0) st.kernel = line.slice(7);
        else if (line.indexOf('sysfs=') === 0)  st.sysfs = line.slice(6);
        else if (line.indexOf('writable=') === 0) st.writable = line.slice(9);
        else if (line.indexOf('target=') === 0)   st.targets.push(line.slice(7));
        else if (line.indexOf('pkg=') === 0)      st.pkgs.push(line.slice(4));
        else if (line.indexOf('uidmap ') === 0) {
            var m = line.slice(6).split(' ');
            st.uidMap[m[0]] = m[1] || 'none';
        }
    });
    return st;
}

/* ---------- rendering ---------- */

function renderBanner() {
    var b = $('banner');
    if (!(window.ksu && typeof window.ksu.exec === 'function')) {
        b.className = 'banner err';
        b.innerHTML = '<span class="ms">error</span><span>非 KernelSU WebUI 环境，无法执行命令</span>';
        return;
    }
    if (state.sysfs === '0') {
        b.className = 'banner err';
        b.innerHTML = '<span class="ms">error</span><span>内核未提供 /sys/kernel/uid_path_filter —— 请确认已刷入 r6 内核</span>';
    } else if (state.writable === '0') {
        b.className = 'banner err';
        b.innerHTML = '<span class="ms">error</span><span>sysfs 节点不可写（SELinux 拒绝），详见诊断</span>';
    } else if (state.rules.length === 0) {
        b.className = 'banner warn';
        b.innerHTML = '<span class="ms">info</span><span>内核规则表为空，点击右下角"保存并应用"</span>';
    } else {
        b.className = 'banner ok';
        b.innerHTML = '<span class="ms">check_circle</span><span>已生效 ' + state.rules.length + ' 条规则' +
            (state.kernel ? '（内核 ' + esc(state.kernel) + '）' : '') + '</span>';
    }
}

function renderSubs() {
    $('targetsSub').textContent = state.targets.length
        ? state.targets.length + ' 个应用 · 点击管理'
        : '未设置 · 点击管理';
    $('pkgsSub').textContent = state.pkgs.length
        ? state.pkgs.length + ' 个目录 · 点击管理'
        : '未设置 · 点击管理';
    $('rulesSub').textContent = state.rules.length
        ? '内核表中 ' + state.rules.length + ' 条 · 点击查看'
        : '暂无规则 · 点击查看';
}

function setBusy(busy) {
    var btn = $('btnApply');
    btn.disabled = busy;
    $('applyLabel').textContent = busy ? '应用中…' : '保存并应用';
}

async function refresh() {
    var r = await run('status');
    if (r.out.indexOf('OK') !== 0) {
        state.sysfs = '?';
        state.writable = '?';
        state.rules = [];
        renderBanner();
        toast(r.out || r.err || 'status failed', true);
        return;
    }
    var st = parseStatus(r.out);
    state.sysfs = st.sysfs;
    state.writable = st.writable;
    state.rules = st.rules;
    state.kernel = st.kernel;
    state.module = st.module;
    state.uidMap = st.uidMap;
    if (!state.dirty) {
        state.targets = st.targets;
        state.pkgs = st.pkgs;
    }
    renderBanner();
    renderSubs();
}

/* ---------- app picker ---------- */

var pickerMode = 't';
var pickerSel = {};

function labelOf(pkg) {
    return state.labels[pkg] || pkg;
}

async function ensureApps() {
    if (state.apps) return;
    var r = await run('apps');
    state.apps = [];
    if (r.out.indexOf('OK') === 0) {
        r.out.split('\n').forEach(function (l) {
            var m = l.match(/^(\S+) (\d+)$/);
            if (m) state.apps.push({ pkg: m[1], uid: m[2] });
        });
    }
}

async function ensureLabels() {
    if (state.labelsLoaded) return;
    var r = await run('labels');
    state.labels = {};
    if (r.out.indexOf('OK') === 0) {
        var body = r.out.slice(r.out.indexOf('\n') + 1);
        try {
            JSON.parse(body).forEach(function (a) {
                if (a && a.pkg) state.labels[a.pkg] = a.label || a.pkg;
            });
        } catch (e) { /* fall back to package names */ }
    }
    state.labelsLoaded = true;
}

function li(pkg, uid) {
    var b = document.createElement('button');
    b.className = 'li';
    var ic = document.createElement('span');
    ic.className = 'ms';
    ic.textContent = pickerSel[pkg] ? 'check_box' : 'check_box_outline_blank';
    var txt = document.createElement('div');
    txt.className = 'li-text';
    var lab = document.createElement('span');
    lab.className = 'li-label';
    lab.textContent = labelOf(pkg);
    var sub = document.createElement('span');
    sub.className = 'li-pkg';
    sub.textContent = uid && uid !== '未安装' ? pkg + ' · ' + uid : pkg;
    txt.appendChild(lab);
    txt.appendChild(sub);
    b.appendChild(ic);
    b.appendChild(txt);
    b.onclick = function () {
        pickerSel[pkg] = !pickerSel[pkg];
        ic.textContent = pickerSel[pkg] ? 'check_box' : 'check_box_outline_blank';
    };
    return b;
}

function renderPicker(q) {
    var box = $('pickerList');
    box.innerHTML = '';
    var ql = q.trim().toLowerCase();
    var seen = {};
    var entries = [];
    state.apps.forEach(function (a) {
        seen[a.pkg] = true;
        entries.push({ pkg: a.pkg, uid: a.uid });
    });
    Object.keys(pickerSel).forEach(function (p) {
        if (!seen[p]) {
            var uid = state.uidMap[p] && state.uidMap[p] !== 'none'
                ? state.uidMap[p]
                : '未安装';
            entries.push({ pkg: p, uid: uid });
        }
    });
    if (ql) {
        entries = entries.filter(function (e) {
            return e.pkg.toLowerCase().indexOf(ql) >= 0 ||
                (state.labels[e.pkg] || '').toLowerCase().indexOf(ql) >= 0;
        });
    }
    var sel = [], unsel = [];
    entries.forEach(function (e) {
        (pickerSel[e.pkg] ? sel : unsel).push(e);
    });
    var byLabel = function (a, b) {
        return labelOf(a.pkg).localeCompare(labelOf(b.pkg), 'zh');
    };
    sel.sort(byLabel);
    unsel.sort(byLabel);
    sel.forEach(function (e) { box.appendChild(li(e.pkg, e.uid)); });
    unsel.forEach(function (e) { box.appendChild(li(e.pkg, e.uid)); });
    if (!box.children.length) {
        box.innerHTML = '<p class="empty">没有匹配的应用，可在下方手动输入包名</p>';
    }
}

async function openPicker(mode) {
    pickerMode = mode;
    pickerSel = {};
    $('pickerTitle').textContent = mode === 't' ? '管理目标应用' : '管理隐藏应用';
    $('pickerSearch').value = '';
    $('manualInput').value = '';
    var existing = mode === 't' ? state.targets : state.pkgs;
    existing.forEach(function (p) { pickerSel[p] = true; });
    $('pickerScrim').hidden = false;
    $('pickerList').innerHTML = '<p class="empty">加载中…</p>';
    await ensureApps();
    renderPicker('');
    ensureLabels().then(function () {
        renderPicker($('pickerSearch').value);
    });
}

function sameSet(a, b) {
    if (a.length !== b.length) return false;
    var s = {};
    a.forEach(function (x) { s[x] = 1; });
    return b.every(function (x) { return s[x]; });
}

function pickerOk() {
    var next = [];
    Object.keys(pickerSel).forEach(function (p) {
        if (pickerSel[p]) next.push(p);
    });
    var list = pickerMode === 't' ? state.targets : state.pkgs;
    if (!sameSet(next, list)) state.dirty = true;
    list.length = 0;
    next.forEach(function (p) { list.push(p); });
    $('pickerScrim').hidden = true;
    renderSubs();
}

function addManual() {
    var v = $('manualInput').value.trim();
    if (!v) return;
    if (!/^[A-Za-z0-9._]+$/.test(v)) { toast('包名格式不正确', true); return; }
    pickerSel[v] = true;
    $('manualInput').value = '';
    renderPicker($('pickerSearch').value);
}

/* ---------- apply ---------- */

async function saveAndApply() {
    if (!state.targets.length) { toast('至少需要一个目标应用', true); return; }
    if (!state.pkgs.length) { toast('至少需要一个隐藏应用', true); return; }

    var lines = [];
    state.targets.forEach(function (t) { lines.push('target=' + t); });
    state.pkgs.forEach(function (p) { lines.push('pkg=' + p); });
    var b64;
    try { b64 = btoa(lines.join('\n') + '\n'); }
    catch (e) { toast('编码失败', true); return; }

    setBusy(true);
    var r = await run('save ' + b64);
    if (r.out.indexOf('OK') !== 0) {
        setBusy(false);
        toast('保存失败: ' + (r.out || r.err), true);
        return;
    }
    r = await run('apply');
    setBusy(false);
    if (r.out.indexOf('OK') !== 0) {
        toast('应用失败: ' + (r.out || r.err), true);
        await refresh();
        return;
    }
    var applied = (r.out.match(/applied=(\d+)/) || [])[1] || '?';
    var skipped = (r.out.match(/skipped:(.*)/) || [])[1];
    state.dirty = false;
    toast('已应用 ' + applied + ' 条规则（已回读内核确认）' +
        (skipped ? '；未安装已跳过: ' + skipped.trim() : ''));
    await refresh();
}

/* ---------- dialogs ---------- */

function openRules() {
    $('rulesDlgSub').textContent = state.kernel ? '内核 ' + state.kernel : '';
    $('rulesPre').textContent = state.rules.length
        ? state.rules.join('\n')
        : '（空）';
    $('rulesScrim').hidden = false;
}

async function openDiag() {
    var uidLine = state.targets.map(function (t) {
        return t + '=' + (state.uidMap[t] || 'none');
    }).join(', ');
    $('diagInfo').textContent =
        '模块 ' + (state.module || '?') + ' · 内核 ' + (state.kernel || '?') +
        '\nsysfs=' + state.sysfs + '  writable=' + state.writable +
        '\n目标 UID: ' + (uidLine || '无');
    $('diagLog').textContent = '读取日志…';
    $('diagScrim').hidden = false;
    var r = await run('log');
    var body = r.out.indexOf('OK') === 0
        ? r.out.split('\n').slice(1).join('\n')
        : (r.out || r.err);
    $('diagLog').textContent = body || '（无日志）';
}

/* ---------- init ---------- */

window.addEventListener('DOMContentLoaded', async function () {
    $('btnRefresh').onclick = function () { refresh(); };
    $('btnTargetDlg').onclick = function () { openPicker('t'); };
    $('btnPkgDlg').onclick = function () { openPicker('p'); };
    $('btnApply').onclick = saveAndApply;
    $('btnRules').onclick = openRules;
    $('btnDiag').onclick = openDiag;

    ['pickerScrim', 'rulesScrim', 'diagScrim'].forEach(function (id) {
        $(id).addEventListener('click', function (e) {
            if (e.target === $(id)) $(id).hidden = true;
        });
    });
    $('pickerCancel').onclick = function () { $('pickerScrim').hidden = true; };
    $('pickerOk').onclick = pickerOk;
    $('pickerSearch').addEventListener('input', function () { renderPicker(this.value); });
    $('manualAdd').onclick = addManual;
    $('manualInput').addEventListener('keydown', function (e) {
        if (e.key === 'Enter') addManual();
    });
    $('rulesClose').onclick = function () { $('rulesScrim').hidden = true; };
    $('diagClose').onclick = function () { $('diagScrim').hidden = true; };
    $('diagRefresh').onclick = openDiag;
    $('snackbar').onclick = function () { this.hidden = true; };

    if (window.ksu && window.ksu.fullScreen) {
        try { window.ksu.fullScreen(false); } catch (e) { /* optional */ }
    }
    if (!(window.ksu && typeof window.ksu.exec === 'function')) {
        $('btnApply').disabled = true;
    }
    await refresh();
});
