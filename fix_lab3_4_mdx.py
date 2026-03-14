import re
import os

def process_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        text = f.read()

    # For 03-trap-and-timer.mdx
    if '03-trap-and-timer.mdx' in path:
        text = re.sub(r'#fix_02\.py\s*\n--------，', '为了实现系统时钟，', text)
        text = re.sub(r'--------断信号，如果我们屏蔽了“听觉”，', '这就意味着我们需要手动开启接收时钟中断信号，如果我们屏蔽了“听觉”，', text)
        text = re.sub(r'python3 fix_01\.`main\.rs`）阶段，这些环节可谓环环相扣：', '因此，在进入 `main.rs` 阶段，这些环节可谓环环相扣：', text)
        text = re.sub(r'--------断，还是应用程序主动请求让出，', '无论是时钟中断，还是应用程序主动请求让出，', text)
        text = re.sub(r'fix_02\.py --------被称为\*\*机制与策略分离\*\*', '这种设计被称为**机制与策略分离**', text)
        text = re.sub(r'python3 fix_01\.py Trap 和时钟驱动任务流转的底层蓝图已在你面前全部展开！', '至此，Trap 和时钟驱动任务流转的底层蓝图已在你面前全部展开！', text)
        text = re.sub(r'--------\n  │  （发生', '  │  （发生', text)
        text = re.sub(r'python3 fix_01\.py fix_02\.py\s*', '（回到用户程序，应用程序从断点处继续往下执行）\n', text)
        text = re.sub(r'fix_0[123]\.py\s*', '', text) 

    # For 04-practice.mdx (Lab 3)
    if 'lab3' in path and '04-practice.mdx' in path:
        text = re.sub(r'#\npython3 fix_01\.py\s*', '', text)
        text = re.sub(r'python3 fix_01\.py\s*', '', text)
        text = re.sub(r'\.devcontainer.*?(ustb-os-tutorial|ustb-os-kernel)\s*', '', text)
        text = re.sub(r'fix_0[123]\.py\s*', '', text)
        text = re.sub(r'--------单道按顺序执行的批处理模样了。', '这就又退化成单道按顺序执行的批处理模样了。', text)
        text = re.sub(r'--------最重要的一块拼图，实现了操作系统历史上关键的时间片轮转壮举！', '你已经补全了分时多任务系统中最重要的一块拼图，实现了操作系统历史上关键的时间片轮转壮举！', text)

    # For 01-overview.mdx
    if '01-overview.mdx' in path:
        text = re.sub(r'--------，所有用户程序被预先加载到物理内存的固定位置', '在前面的实验中，所有用户程序被预先加载到物理内存的固定位置（', text)
        text = re.sub(r'\*\*虚拟地址到\n\*\*，解决上述所有问题', '**虚拟地址到物理地址的映射**，解决上述所有问题', text)
        text = re.sub(r'\.devcontainer.*?(ustb-os-kernel|ustb-os-tutorial)[/\s]*RISC-V 的 \*\*SV39\*\* 分页模式', '本章采用 RISC-V 的 **SV39** 分页模式', text)
        text = re.sub(r'\.devcontainer.*?(ustb-os-kernel|ustb-os-tutorial)[/\s]*39 位有效，其余高位必须是第 38 位的符号扩展', '虽然虚拟地址是 64 位，但在 SV39 模式下只有低 39 位有效，其余高位必须是第 38 位的符号扩展', text)
        text = re.sub(r' CPU 会触发异常。这正是为什么内核地址空间被放在高地址（全 1 扩展），\n 0 扩展）。', '否则 CPU 会触发异常。这正是为什么内核地址空间被放在高地址（全 1 扩展），而用户地址空间被放在低地址（全 0 扩展）。', text)
        text = re.sub(r'\.devcontainer.*?(ustb-os-kernel|ustb-os-tutorial)[/\s]*-512项 × 8字节 = 4096字节），', '每一级页表刚好占用一个物理页（512项 × 8字节 = 4096字节），\n最终支持', text)
        text = re.sub(r'#\n\.devcontainer.*?(ustb-os-kernel|ustb-os-tutorial)[/\s]*Trap 从用户态切换到内核态时，CPU 会切换页表，', '当 Trap 从用户态切换到内核态时，CPU 会切换页表，但这不影响', text)

    # For 02-address-and-frame.mdx
    if '02-address-and-frame.mdx' in path:
        text = re.sub(r'\.devcontainer.*?(ustb-os-kernel|ustb-os-tutorial)[/\s]*-os-tutorial\s*', '', text)
        text = re.sub(r'\.devcontainer.*?(ustb-os-kernel|ustb-os-tutorial)[/\s]*VPN，`indexes\(\)` 结果为 `\[VPN\[2\], VPN\[1\], VPN\[0\]\]`，分别是', '例如对于一个 VPN，`indexes()` 结果为 `[VPN[2], VPN[1], VPN[0]]`，分别是三个级别的页表索引。', text)
        text = re.sub(r'  内核代码数据  │         空闲物理帧（供分配）               │\n  \[0, ekernel\)', '  内核代码数据  │         空闲物理帧（供分配）               │\n  [0, ekernel)', text) # Keep format

    # For 03-page-table.mdx
    if '03-page-table.mdx' in path:
        text = re.sub(r'\.devcontainer.*?ustb-os-(?:kernel|tutorial)[/\s]*-[/\s]*`kernel/src/mm/page_table\.rs`。', '这四个函数都位于 `kernel/src/mm/page_table.rs`。', text)
        text = re.sub(r'--------间节点 PTE（V 位置 1，PPN 指向新帧）。', '并初始化作为中间节点 PTE（V 位置 1，PPN 指向新帧）。', text)
        text = re.sub(r'--------查找', '1. 查找', text)
        text = re.sub(r'\.devcontainer.*?ustb-os-(?:kernel|tutorial)[/\s]*V 位，\*\*不设置 R/W/X/U\*\* 标志——这标志着它是中间节点。', '创建新节点时，我们仅置位 V 位，**不设置 R/W/X/U** 标志——这标志着它是中间节点。', text)
        text = re.sub(r' PTE 的引用，不关心它是否 valid（由 `map` 来写入）。', '它会返回叶子节点 PTE 的引用，不关心它是否 valid（由 `map` 来写入）。', text)
        text = re.sub(r'--------间节点的帧由 `PageTable\.frames` 持有', '中间节点的帧由 `PageTable.frames` 持有', text)
        text = re.sub(r'\.devcontainer.*?ustb-os-(?:kernel|tutorial)[/\s]*`kernel/src/mm/page_table\.rs`。', '请实现以下这四个函数，它们都位于 `kernel/src/mm/page_table.rs`。', text)
        text = re.sub(r'--------的数据复制。', '实现用户物理页内的数据复制。', text)
        text = re.sub(r'#\n', '', text)

    # For 04-practice.mdx (Lab 4)
    if 'lab4' in path and '04-practice.mdx' in path:
        text = re.sub(r'\.devcontainer.*?(ustb-os-kernel|ustb-os-tutorial)[/\s]*', '', text)
        text = re.sub(r'Ustb\n panic。', '否则将导致系统 panic。', text)
        text = re.sub(r'--------找到并阅读以下函数/方法：', '你需要找到并阅读以下函数/方法：', text)
        text = re.sub(r'--------）写出伪代码，再翻译为 Rust 实现。', '请先（在纸上或脑海中）写出伪代码，再翻译为 Rust 实现。', text)
        text = re.sub(r'#\n', '', text)

    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)
    print(f"Processed {path}")

base = '/home/ustb-os/ustb-os-tutorial/src/content/docs/'
paths = [
    'lab3/03-trap-and-timer.mdx',
    'lab3/04-practice.mdx',
    'lab4/01-overview.mdx',
    'lab4/02-address-and-frame.mdx',
    'lab4/03-page-table.mdx',
    'lab4/04-practice.mdx'
]

for p in paths:
    process_file(os.path.join(base, p))
