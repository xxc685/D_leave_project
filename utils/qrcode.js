/**
 * utils/qrcode.js
 * 轻量级二维码生成器 — 微信小程序 Canvas 2D
 *
 * 特性：Byte 模式 / Version 1~5 自动选择 / L 级纠错 / 8 种掩码评分 / 格式信息编码
 * 用法：const qrcode = require('qrcode.js'); qrcode.drawToCanvas(ctx, text, size);
 */

// ═══════════════════════ GF(256) 运算表 ═══════════════════════
var EXP = new Uint8Array(512);
var LOG = new Uint8Array(256);
(function () {
  var x = 1;
  for (var i = 0; i < 255; i++) {
    EXP[i] = x;
    EXP[i + 255] = x; // 双倍长度便于乘法越界取模
    LOG[x] = i;
    x <<= 1;
    if (x & 0x100) x ^= 0x11D; // 本原多项式 x^8 + x^4 + x^3 + x^2 + 1
  }
  LOG[1] = 0;
})();

function gmul(a, b) {
  if (!a || !b) return 0;
  return EXP[LOG[a] + LOG[b]];
}

// ═══════════════════════ 多项式运算 ═══════════════════════
function polyMul(p, q) {
  var r = new Uint8Array(p.length + q.length - 1);
  for (var i = 0; i < p.length; i++) {
    for (var j = 0; j < q.length; j++) {
      r[i + j] ^= gmul(p[i], q[j]);
    }
  }
  return r;
}

var GEN_CACHE = {};
function rsGenPoly(ecCount) {
  if (GEN_CACHE[ecCount]) return GEN_CACHE[ecCount];
  var g = new Uint8Array([1]);
  for (var i = 0; i < ecCount; i++) {
    g = polyMul(g, new Uint8Array([1, EXP[i]]));
  }
  GEN_CACHE[ecCount] = g;
  return g;
}

/**
 * Reed-Solomon 纠错编码
 * data: Uint8Array 消息码字
 * ecCount: 纠错码字数量
 * 返回 ecCount 个纠错码字
 */
function rsEncode(data, ecCount) {
  var gen = rsGenPoly(ecCount);
  var msg = new Uint8Array(data.length + ecCount);
  msg.set(data);
  for (var i = 0; i < data.length; i++) {
    if (!msg[i]) continue;
    var f = LOG[msg[i]];
    for (var j = 0; j < gen.length; j++) {
      msg[i + j] ^= EXP[LOG[gen[j]] + f];
    }
  }
  return msg.slice(data.length);
}

// ═══════════════════════ 版本参数表 ═══════════════════════
// [总码字数, 数据码字数(L), 纠错码字数(L), 模块数]
var VER = [
  null,
  [26, 19, 7, 21],    // Version 1
  [44, 34, 10, 25],   // Version 2
  [70, 55, 15, 29],   // Version 3
  [100, 80, 20, 33],  // Version 4
  [134, 108, 26, 37], // Version 5
];

/**
 * 获取对齐图案中心坐标（排除与探测图案重叠的位置）
 */
function getAlignCenters(ver) {
  if (ver === 1) return [];
  var posMap = { 2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30] };
  var positions = posMap[ver] || [];
  var mod = VER[ver][3];
  var centers = [];
  for (var ri = 0; ri < positions.length; ri++) {
    for (var ci = 0; ci < positions.length; ci++) {
      var r = positions[ri], c = positions[ci];
      // 跳过与三个探测图形重叠的交点
      if (r < 9 && c < 9) continue;           // 左上
      if (r < 9 && c > mod - 9) continue;     // 右上
      if (r > mod - 9 && c < 9) continue;     // 左下
      centers.push([r, c]);
    }
  }
  return centers;
}

// ═══════════════════════ 格式信息 ═══════════════════════
// EC Level L (01) + Mask 0-7，BCH(15,5) 编码后 XOR 0x5412
// 索引即掩码编号，值为 15-bit 数组（高位在前）
var FMT_BITS = [
  [1,1,1,0,1,1,1,1,1,0,0,0,1,0,0], // mask 0
  [1,1,1,0,0,1,0,1,1,1,1,0,0,1,1], // mask 1
  [1,1,1,1,1,0,1,1,0,1,0,1,0,1,0], // mask 2
  [1,1,1,1,0,0,0,1,0,0,1,1,0,0,1], // mask 3
  [1,1,0,0,1,1,0,0,0,1,0,1,1,1,1], // mask 4
  [1,1,0,0,0,1,1,0,0,0,1,1,0,0,0], // mask 5
  [1,1,0,1,1,0,0,0,1,0,0,0,0,0,1], // mask 6
  [1,1,0,1,0,0,1,0,1,1,0,1,1,1,0], // mask 7
];

// ═══════════════════════ 自动选择版本 ═══════════════════════
function pickVersion(textLen) {
  for (var v = 1; v <= 5; v++) {
    // Byte 模式开销：4(模式) + 8(长度) + textLen*8 + 4(终止符)
    var needBits = 4 + 8 + textLen * 8 + 4;
    if (needBits <= VER[v][1] * 8) return v;
  }
  return 5; // 兜底
}

// ═══════════════════════ Byte 模式编码 ═══════════════════════
function encodeBits(text, version) {
  var cap = VER[version][1]; // 数据码字数
  var bits = [];

  // 模式指示符：0100 (Byte)
  bits.push(0); bits.push(1); bits.push(0); bits.push(0);

  // 字符计数（V1-9 固定 8 位）
  var len = text.length;
  for (var i = 7; i >= 0; i--) bits.push((len >> i) & 1);

  // 数据字节
  for (var bi = 0; bi < len; bi++) {
    var byte = text.charCodeAt(bi) & 0xFF;
    for (var j = 7; j >= 0; j--) bits.push((byte >> j) & 1);
  }

  // 终止符（最多 4 位 0）
  var termLen = Math.min(4, cap * 8 - bits.length);
  for (var ti = 0; ti < termLen; ti++) bits.push(0);

  // 位填充到 8 的倍数
  while (bits.length % 8 !== 0) bits.push(0);

  // 码字填充（交替 0xEC / 0x11）
  var padBytes = [0xEC, 0x11];
  var pi = 0;
  while (bits.length < cap * 8) {
    var pb = padBytes[pi % 2];
    pi++;
    for (var k = 7; k >= 0; k--) bits.push((pb >> k) & 1);
  }

  return bits;
}

// ═══════════════════════ 空矩阵 + 功能模块 ═══════════════════════
function buildMatrix(version) {
  var sz = VER[version][3];
  var m = [];
  var mark = new Int8Array(sz * sz); // 1=功能模块（不参与掩码）

  for (var r = 0; r < sz; r++) {
    m[r] = new Int8Array(sz);
  }

  function set(rr, cc, v, isFunc) {
    if (rr >= 0 && rr < sz && cc >= 0 && cc < sz) {
      m[rr][cc] = v;
      if (isFunc) mark[rr * sz + cc] = 1;
    }
  }

  // --- 位置探测图形（3 个角） ---
  var finders = [[0, 0], [0, sz - 7], [sz - 7, 0]];
  for (var fi = 0; fi < finders.length; fi++) {
    var fr = finders[fi][0], fc = finders[fi][1];
    for (var dr = -1; dr <= 7; dr++) {
      for (var dc = -1; dc <= 7; dc++) {
        var rr = fr + dr, cc = fc + dc;
        if (rr < 0 || rr >= sz || cc < 0 || cc >= sz) continue;
        if (dr >= 0 && dr <= 6 && dc >= 0 && dc <= 6) {
          // 7×7 探测图形
          var black =
            dr === 0 || dr === 6 || dc === 0 || dc === 6 ||
            (dr >= 2 && dr <= 4 && dc >= 2 && dc <= 4);
          set(rr, cc, black ? 1 : 0, true);
        } else {
          // 分隔符（白色）
          set(rr, cc, 0, true);
        }
      }
    }
  }

  // --- 时序图案 ---
  for (var ti = 8; ti < sz - 8; ti++) {
    set(6, ti, ti % 2 === 0 ? 1 : 0, true);
    set(ti, 6, ti % 2 === 0 ? 1 : 0, true);
  }

  // --- 对齐图案 ---
  var acs = getAlignCenters(version);
  for (var ai = 0; ai < acs.length; ai++) {
    var ar = acs[ai][0], ac = acs[ai][1];
    for (var dr = -2; dr <= 2; dr++) {
      for (var dc = -2; dc <= 2; dc++) {
        var black =
          dr === -2 || dr === 2 || dc === -2 || dc === 2 ||
          (dr === 0 && dc === 0);
        set(ar + dr, ac + dc, black ? 1 : 0, true);
      }
    }
  }

  // --- 预留格式信息区域 ---
  for (var c = 0; c <= 8; c++) set(8, c, 0, true);
  for (var rr = 0; rr <= 8; rr++) set(rr, 8, 0, true);
  for (var cc = sz - 8; cc < sz; cc++) set(8, cc, 0, true);
  for (var rr2 = sz - 7; rr2 < sz; rr2++) set(rr2, 8, 0, true);

  // --- 暗模块（永远为黑） ---
  set(sz - 8, 8, 1, true);

  return { matrix: m, mark: mark, size: sz };
}

// ═══════════════════════ 之字形数据位填充 ═══════════════════════
function placeBits(matrix, mark, size, bits) {
  var col = size - 1;
  var up = true;
  var bi = 0;

  while (col > 0) {
    // 跳过垂直时序图案列
    if (col === 6) col--;

    var startRow, endRow, step;
    if (up) {
      startRow = size - 1;
      endRow = -1;
      step = -1;
    } else {
      startRow = 0;
      endRow = size;
      step = 1;
    }

    for (var row = startRow; row !== endRow; row += step) {
      // 每行放置两个模块（右列 + 左列）
      for (var dc = 0; dc >= -1; dc--) {
        var cc = col + dc;
        if (cc < 0 || cc >= size) continue;
        if (mark[row * size + cc]) continue; // 跳过功能模块
        matrix[row][cc] = bi < bits.length ? bits[bi] : 0;
        bi++;
      }
    }

    up = !up;
    col -= 2;
  }
}

// ═══════════════════════ 掩码模式 ═══════════════════════
function maskCond(row, col, pat) {
  switch (pat) {
    case 0: return (row + col) % 2 === 0;
    case 1: return row % 2 === 0;
    case 2: return col % 3 === 0;
    case 3: return (row + col) % 3 === 0;
    case 4: return (Math.floor(row / 2) + Math.floor(col / 3)) % 2 === 0;
    case 5: return (row * col) % 2 + (row * col) % 3 === 0;
    case 6: return ((row * col) % 2 + (row * col) % 3) % 2 === 0;
    case 7: return ((row + col) % 2 + (row * col) % 3) % 2 === 0;
  }
  return false;
}

function applyMask(matrix, mark, size, pat) {
  var masked = [];
  for (var r = 0; r < size; r++) {
    masked[r] = new Int8Array(matrix[r]);
  }
  for (var r = 0; r < size; r++) {
    for (var c = 0; c < size; c++) {
      if (mark[r * size + c]) continue;
      if (maskCond(r, c, pat)) masked[r][c] ^= 1;
    }
  }
  return masked;
}

// ═══════════════════════ 掩码罚分评估 ═══════════════════════
function evalPenalty(mtx, size) {
  var p = 0;

  // 规则 1：同行/列连续 5+ 同色模块
  for (var r = 0; r < size; r++) {
    var run = 1;
    for (var c = 1; c < size; c++) {
      if (mtx[r][c] === mtx[r][c - 1]) {
        run++;
      } else {
        if (run >= 5) p += 3 + (run - 5);
        run = 1;
      }
    }
    if (run >= 5) p += 3 + (run - 5);
  }
  for (var c = 0; c < size; c++) {
    var runCol = 1;
    for (var r = 1; r < size; r++) {
      if (mtx[r][c] === mtx[r - 1][c]) {
        runCol++;
      } else {
        if (runCol >= 5) p += 3 + (runCol - 5);
        runCol = 1;
      }
    }
    if (runCol >= 5) p += 3 + (runCol - 5);
  }

  // 规则 2：2×2 同色方块
  for (var r = 0; r < size - 1; r++) {
    for (var c = 0; c < size - 1; c++) {
      if (
        mtx[r][c] === mtx[r + 1][c] &&
        mtx[r][c] === mtx[r][c + 1] &&
        mtx[r][c] === mtx[r + 1][c + 1]
      ) {
        p += 3;
      }
    }
  }

  // 规则 3：1:1:3:1:1 模式 1011101，任意一侧 4 白模块
  var pat = [1, 0, 1, 1, 1, 0, 1];
  // 水平扫描
  for (var r = 0; r < size; r++) {
    for (var c = 0; c <= size - 7; c++) {
      var match = true;
      for (var k = 0; k < 7; k++) {
        if (mtx[r][c + k] !== pat[k]) { match = false; break; }
      }
      if (!match) continue;
      // 检查前 4
      var beforeWhite = true;
      for (var k = 1; k <= 4; k++) {
        if (c - k >= 0 && mtx[r][c - k] !== 0) { beforeWhite = false; break; }
      }
      // 检查后 4
      var afterWhite = true;
      for (var k = 0; k < 4; k++) {
        if (c + 7 + k < size && mtx[r][c + 7 + k] !== 0) { afterWhite = false; break; }
      }
      if (beforeWhite || afterWhite) p += 40;
    }
  }
  // 垂直扫描
  for (var c = 0; c < size; c++) {
    for (var r = 0; r <= size - 7; r++) {
      var match2 = true;
      for (var k = 0; k < 7; k++) {
        if (mtx[r + k][c] !== pat[k]) { match2 = false; break; }
      }
      if (!match2) continue;
      var beforeWhite2 = true;
      for (var k = 1; k <= 4; k++) {
        if (r - k >= 0 && mtx[r - k][c] !== 0) { beforeWhite2 = false; break; }
      }
      var afterWhite2 = true;
      for (var k = 0; k < 4; k++) {
        if (r + 7 + k < size && mtx[r + 7 + k][c] !== 0) { afterWhite2 = false; break; }
      }
      if (beforeWhite2 || afterWhite2) p += 40;
    }
  }

  // 规则 4：暗模块比例偏差
  var dark = 0;
  var total = size * size;
  for (var r = 0; r < size; r++) {
    for (var c = 0; c < size; c++) {
      if (mtx[r][c]) dark++;
    }
  }
  var ratio = dark / total;
  p += Math.floor(Math.abs(ratio - 0.5) * 20) * 10;

  return p;
}

// ═══════════════════════ 格式信息写入 ═══════════════════════
function placeFormat(mtx, size, maskIdx) {
  var f = FMT_BITS[maskIdx];

  // 左上角（绕探测图形）— 15 bits
  mtx[8][0] = f[0];   mtx[8][1] = f[1];   mtx[8][2] = f[2];
  mtx[8][3] = f[3];   mtx[8][4] = f[4];   mtx[8][5] = f[5];
  mtx[8][7] = f[6];   // 跳过 (8,6)=时序
  mtx[8][8] = f[7];
  mtx[7][8] = f[8];   // 跳过 (6,8)=时序
  mtx[5][8] = f[9];   mtx[4][8] = f[10];
  mtx[3][8] = f[11];  mtx[2][8] = f[12];
  mtx[1][8] = f[13];  mtx[0][8] = f[14];

  // 右上角 — bits 14-7
  mtx[8][size - 1] = f[0];  mtx[8][size - 2] = f[1];
  mtx[8][size - 3] = f[2];  mtx[8][size - 4] = f[3];
  mtx[8][size - 5] = f[4];  mtx[8][size - 6] = f[5];
  mtx[8][size - 7] = f[6];  mtx[8][size - 8] = f[7];

  // 左下角 — bits 6-0
  mtx[size - 7][8] = f[8];   mtx[size - 6][8] = f[9];
  mtx[size - 5][8] = f[10];  mtx[size - 4][8] = f[11];
  mtx[size - 3][8] = f[12];  mtx[size - 2][8] = f[13];
  mtx[size - 1][8] = f[14];
}

// ═══════════════════════ 主编码 ═══════════════════════
function encode(text) {
  var version = pickVersion(text.length);
  var bits = encodeBits(text, version);

  // 位流 → 码字数组
  var dataCWLen = bits.length / 8;
  var dataCW = new Uint8Array(dataCWLen);
  for (var i = 0; i < dataCWLen; i++) {
    var cw = 0;
    for (var j = 0; j < 8; j++) {
      cw = (cw << 1) | (bits[i * 8 + j] || 0);
    }
    dataCW[i] = cw;
  }

  // RS 纠错编码
  var ecCW = rsEncode(dataCW, VER[version][2]);

  // 合并数据 + 纠错码字
  var allCW = new Uint8Array(dataCW.length + ecCW.length);
  allCW.set(dataCW);
  allCW.set(ecCW, dataCW.length);

  // 码字 → 位流
  var allBits = [];
  for (var ci = 0; ci < allCW.length; ci++) {
    for (var j = 7; j >= 0; j--) {
      allBits.push((allCW[ci] >> j) & 1);
    }
  }

  // 构建空矩阵（含功能模块）
  var bm = buildMatrix(version);

  // 放置数据位
  placeBits(bm.matrix, bm.mark, bm.size, allBits);

  // 掩码评估 & 选择最优
  var bestMask = 0;
  var bestScore = Infinity;
  var bestMatrix = null;
  for (var mask = 0; mask < 8; mask++) {
    var masked = applyMask(bm.matrix, bm.mark, bm.size, mask);
    var score = evalPenalty(masked, bm.size);
    if (score < bestScore) {
      bestScore = score;
      bestMask = mask;
      bestMatrix = masked;
    }
  }

  // 写入格式信息
  placeFormat(bestMatrix, bm.size, bestMask);

  return { matrix: bestMatrix, size: bm.size, version: version };
}

// ═══════════════════════ Canvas 2D 绘制 ═══════════════════════
/**
 * 将二维码绘制到 Canvas 上下文
 * @param {CanvasRenderingContext2D} ctx    - Canvas 2D 上下文
 * @param {string}                 text    - 要编码的文本
 * @param {number}                 canvasSize - 画布逻辑尺寸（像素）
 */
function drawToCanvas(ctx, text, canvasSize) {
  var result = encode(text);
  var matrix = result.matrix;
  var qrSize = result.size;
  var quiet = 4; // 4 模块静区
  var totalModules = qrSize + quiet * 2;
  var modulePx = Math.floor(canvasSize / totalModules);
  var offset = Math.floor((canvasSize - modulePx * totalModules) / 2);

  // 白色背景
  ctx.fillStyle = '#FFFFFF';
  ctx.fillRect(0, 0, canvasSize, canvasSize);

  // 黑色模块
  ctx.fillStyle = '#000000';
  for (var r = 0; r < qrSize; r++) {
    for (var c = 0; c < qrSize; c++) {
      if (matrix[r][c]) {
        ctx.fillRect(
          offset + (c + quiet) * modulePx,
          offset + (r + quiet) * modulePx,
          modulePx,
          modulePx
        );
      }
    }
  }
}

module.exports = {
  encode: encode,
  drawToCanvas: drawToCanvas
};
