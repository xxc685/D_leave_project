const config = require('../../utils/config');
const qrcode = require('../../utils/qrcode');

Page({
  data: {
    // 身份信息（从全局存储读取）
    isBound: true,
    teacherName: '',
    teacherId: '',

    // 动态班级列表（picker 使用 id / name）
    classList: [],
    classIndex: 0,

    // 历史签到场次
    sessionHistory: [],
    historyLoading: false,

    // 请假审批
    leaveRequests: [],
    leaveLoading: false,
    reviewingLeave: false,

    // 发起参数 (对应ER图字段)
    validDuration: 0,
    needLocation: false,
    radius: 100,
    latitude: null,
    longitude: null,
    qrToken: '',
    currentSessionId: null,

    // [B3] 防重复点击
    generating: false,
    finalizing: false
  },

  onLoad() {
    const id = wx.getStorageSync('id');
    const name = wx.getStorageSync('name');
    if (name && id) {
      this.setData({ teacherName: name, teacherId: id, isBound: true });
      this.loadTeacherClasses();
      this.loadSessionHistory();
      this.loadLeaveRequests();
    }
  },

  onShow() {
    if (this.data.isBound && this.data.teacherId) {
      this.loadSessionHistory();
      this.loadLeaveRequests();
    }
  },

  // --- 动态加载教师课程 ---
  loadTeacherClasses() {
    const teacherId = this.data.teacherId;
    if (!teacherId) return;

    wx.request({
      url: config.API_BASE + '/api/teacher/' + teacherId + '/classes',
      method: 'GET',
      success: (res) => {
        if (res.data.code === 200) {
          const rows = res.data.data || [];
          const classList = rows.map(item => ({
            id: item.class_id,
            name: (item.course_name || '未命名课程') +
              (item.location ? ' · ' + item.location : '') +
              (item.semester ? ' (' + item.semester + ')' : ''),
            class_id: item.class_id,
            course_name: item.course_name,
            location: item.location,
            semester: item.semester
          }));
          this.setData({ classList, classIndex: 0 });
          if (classList.length === 0) {
            wx.showToast({ title: '暂无授课班级', icon: 'none' });
          }
        } else {
          wx.showToast({ title: res.data.message || '课程加载失败', icon: 'none' });
          this.setData({ classList: [], classIndex: 0 });
        }
      },
      fail: () => {
        wx.showToast({ title: '网络请求失败', icon: 'none' });
        this.setData({ classList: [], classIndex: 0 });
      }
    });
  },

  // --- 历史签到场次 ---
  loadSessionHistory() {
    const teacherId = this.data.teacherId;
    if (!teacherId) return;

    this.setData({ historyLoading: true });
    wx.request({
      url: config.API_BASE + '/api/teacher/' + teacherId + '/sessions',
      method: 'GET',
      success: (res) => {
        if (res.data.code === 200) {
          this.setData({ sessionHistory: res.data.data || [] });
        } else {
          wx.showToast({ title: res.data.message || '历史记录加载失败', icon: 'none' });
          this.setData({ sessionHistory: [] });
        }
      },
      fail: () => {
        wx.showToast({ title: '网络请求失败', icon: 'none' });
        this.setData({ sessionHistory: [] });
      },
      complete: () => {
        this.setData({ historyLoading: false });
      }
    });
  },

  // --- 请假审批 ---
  loadLeaveRequests(showToast) {
    const teacherId = this.data.teacherId;
    if (!teacherId || this.data.leaveLoading) return;
    this.setData({ leaveLoading: true });
    wx.request({
      url: config.API_BASE + '/api/teacher/' + teacherId + '/leave_requests',
      method: 'GET',
      success: res => {
        if (res.data.code === 200) {
          const statusMap = {
            pending: { label: '待审批', cls: 'leave-pending' },
            approved: { label: '已批准', cls: 'leave-approved' },
            rejected: { label: '已驳回', cls: 'leave-rejected' }
          };
          const rows = (res.data.data || []).map(item => {
            const state = statusMap[item.status] || { label: item.status, cls: 'leave-pending' };
            return { ...item, status_label: state.label, status_cls: state.cls };
          });
          this.setData({ leaveRequests: rows });
          if (showToast) wx.showToast({ title: '审批列表已刷新', icon: 'success' });
        } else {
          wx.showToast({ title: res.data.message || '请假列表加载失败', icon: 'none' });
        }
      },
      fail: () => wx.showToast({ title: '网络请求失败', icon: 'none' }),
      complete: () => this.setData({ leaveLoading: false })
    });
  },

  refreshLeaveRequests() {
    this.loadLeaveRequests(true);
  },

  reviewLeave(e) {
    if (this.data.reviewingLeave) return;
    const requestId = e.currentTarget.dataset.requestId;
    const action = e.currentTarget.dataset.action;
    const approving = action === 'approve';
    wx.showModal({
      title: approving ? '批准请假' : '驳回请假',
      content: approving ? '可填写审批备注' : '请填写驳回原因',
      editable: true,
      placeholderText: approving ? '审批备注（可选）' : '驳回原因',
      confirmText: approving ? '批准' : '驳回',
      confirmColor: approving ? '#2f7d4a' : '#c0392b',
      success: modalRes => {
        if (!modalRes.confirm) return;
        const remark = (modalRes.content || '').trim();
        if (!approving && !remark) {
          wx.showToast({ title: '请填写驳回原因', icon: 'none' });
          return;
        }
        this.submitLeaveReview(requestId, action, remark);
      }
    });
  },

  submitLeaveReview(requestId, action, reviewRemark) {
    this.setData({ reviewingLeave: true });
    wx.showLoading({ title: '正在提交审批...' });
    wx.request({
      url: config.API_BASE + '/api/leave_requests/' + requestId + '/review',
      method: 'POST',
      header: { 'Content-Type': 'application/json' },
      data: {
        reviewer_id: this.data.teacherId,
        action,
        review_remark: reviewRemark
      },
      success: res => {
        if (res.data.code === 200) {
          wx.showToast({ title: res.data.message || '审批成功', icon: 'success' });
          this.loadLeaveRequests();
        } else {
          wx.showToast({ title: res.data.message || '审批失败', icon: 'none' });
        }
      },
      fail: () => wx.showToast({ title: '网络请求失败', icon: 'none' }),
      complete: () => {
        wx.hideLoading();
        this.setData({ reviewingLeave: false });
      }
    });
  },

  // --- 签到设置与定位逻辑处理 ---
  bindClassChange(e) { this.setData({ classIndex: e.detail.value }); },
  inputDuration(e) { this.setData({ validDuration: e.detail.value }); },
  inputRadius(e) { this.setData({ radius: e.detail.value }); },

  switchLocation(e) {
    const that = this;
    if (e.detail.value) {
      wx.showLoading({ title: '正在获取定位...' });
      wx.getLocation({
        type: 'gcj02',
        success(res) {
          wx.hideLoading();
          that.setData({
            needLocation: true,
            latitude: res.latitude,
            longitude: res.longitude
          });
          wx.showToast({ title: '定位开启成功', icon: 'success' });
        },
        fail() {
          wx.hideLoading();
          that.setData({ needLocation: false, latitude: null, longitude: null });
          wx.showModal({
            title: '定位启动失败',
            content: '未在系统中检测到位置权限声明。若需测试真实定位校验，请在 app.json 中声明权限；否则请直接关闭此开关，进行标准免定位签到测试。',
            showCancel: false
          });
        }
      });
    } else {
      that.setData({ needLocation: false, latitude: null, longitude: null });
    }
  },

  // --- 核心：发起新签到 ---
  generateQRCode() {
    const that = this;
    const validMinutes = parseInt(this.data.validDuration);

    // [B3] 防重复点击
    if (this.data.generating) return;
    this.setData({ generating: true });

    if (!this.data.classList.length) {
      wx.showToast({ title: '请先绑定有授课班级的账号', icon: 'none' });
      this.setData({ generating: false });
      return;
    }

    if (!validMinutes || validMinutes <= 0) {
      wx.showToast({ title: '请设置有效时长', icon: 'none' });
      this.setData({ generating: false });
      return;
    }

    // 定位开关已开启但未获取到有效坐标时拦截
    if (this.data.needLocation) {
      if (!this.data.latitude || !this.data.longitude ||
          this.data.latitude === 0 || this.data.longitude === 0) {
        wx.showModal({
          title: '定位获取失败',
          content: '您已开启定位校验，但尚未获取到有效位置坐标。\n\n请关闭定位开关进行免定位签到，或重试获取定位后再发起签到。',
          showCancel: false
        });
        that.setData({ generating: false });
        return;
      }
    }

    const now = new Date();
    const pad = n => n < 10 ? '0' + n : '' + n;
    const sessionDate = now.getFullYear() + '-' + pad(now.getMonth() + 1) + '-' + pad(now.getDate());
    const startTime = sessionDate + ' ' + pad(now.getHours()) + ':' + pad(now.getMinutes()) + ':' + pad(now.getSeconds());

    const endDate = new Date(now.getTime() + validMinutes * 60000);
    const endTime = endDate.getFullYear() + '-' + pad(endDate.getMonth() + 1) + '-' + pad(endDate.getDate())
      + ' ' + pad(endDate.getHours()) + ':' + pad(endDate.getMinutes()) + ':' + pad(endDate.getSeconds());

    wx.showLoading({ title: '正在发起...' });

    wx.request({
      url: config.API_BASE + '/api/sessions',
      method: 'POST',
      header: { 'Content-Type': 'application/json' },
      data: {
        class_id: that.data.classList[that.data.classIndex].id,
        session_date: sessionDate,
        start_time: startTime,
        end_time: endTime,
        valid_minutes: validMinutes,
        location_latitude: that.data.latitude || 0,
        location_longitude: that.data.longitude || 0,
        location_radius: that.data.radius
      },
      success(res) {
        wx.hideLoading();
        if (res.data.code === 200) {
          that.setData({
            generating: false,
            qrToken: res.data.data.qr_token,
            currentSessionId: res.data.data.session_id
          });
          wx.showToast({ title: '签到发起成功', icon: 'success' });
          that.drawQRCode(res.data.data.qr_token);
          that.loadSessionHistory();
        } else {
          that.setData({ generating: false });
          wx.showToast({ title: res.data.message || '发起失败', icon: 'none' });
        }
      },
      fail() {
        wx.hideLoading();
        that.setData({ generating: false });
        wx.showToast({ title: '网络请求失败', icon: 'none' });
      }
    });
  },

  // --- Canvas 2D 绘制二维码 ---
  drawQRCode(token) {
    if (!token) return;
    const that = this;

    const tryDraw = function (retries) {
      const query = wx.createSelectorQuery();
      query.select('#qrCanvas')
        .fields({ node: true, size: true })
        .exec(function (res) {
          if (res && res[0] && res[0].node) {
            const canvas = res[0].node;
            const ctx = canvas.getContext('2d');
            const displaySize = 250;
            canvas.width = displaySize;
            canvas.height = displaySize;
            ctx.clearRect(0, 0, displaySize, displaySize);
            qrcode.drawToCanvas(ctx, token, displaySize);
          } else if (retries > 0) {
            setTimeout(function () { tryDraw(retries - 1); }, 150);
          } else {
            console.warn('[QR] Canvas 节点获取失败，请刷新重试');
          }
        });
    };

    setTimeout(function () { tryDraw(5); }, 200);
  },

  // --- 保存二维码到相册 ---
  saveQRCode() {
    // 抽取保存到相册的公共逻辑
    const saveToAlbum = function (filePath) {
      wx.saveImageToPhotosAlbum({
        filePath: filePath,
        success: function () {
          wx.showToast({ title: '已保存到相册', icon: 'success' });
        },
        fail: function (err) {
          if (err.errMsg && err.errMsg.indexOf('auth deny') !== -1) {
            wx.showModal({
              title: '相册权限未开启',
              content: '请在设置中允许小程序保存图片到相册。',
              confirmText: '去设置',
              success: function (modalRes) {
                if (modalRes.confirm) {
                  wx.openSetting();
                }
              }
            });
          } else {
            wx.showToast({ title: '保存失败，请重试', icon: 'none' });
          }
        }
      });
    };

    const doExport = function () {
      const query = wx.createSelectorQuery();
      query.select('#qrCanvas')
        .fields({ node: true, size: true })
        .exec(function (canvasRes) {
          if (canvasRes && canvasRes[0] && canvasRes[0].node) {
            wx.canvasToTempFilePath({
              canvas: canvasRes[0].node,
              fileType: 'jpg',
              quality: 0.9,
              success: function (tempRes) {
                saveToAlbum(tempRes.tempFilePath);
              },
              fail: function () {
                wx.showToast({ title: '二维码导出失败，请刷新后重试', icon: 'none' });
              }
            });
          } else {
            wx.showToast({ title: '二维码未就绪，请稍后重试', icon: 'none' });
          }
        });
    };

    // 先检查相册授权状态，避免首次调用就触发 deny
    wx.getSetting({
      success: function (settingRes) {
        const auth = settingRes.authSetting['scope.writePhotosAlbum'];
        if (auth === false) {
          wx.showModal({
            title: '相册权限未开启',
            content: '请在设置中允许小程序保存图片到相册。',
            confirmText: '去设置',
            success: function (modalRes) {
              if (modalRes.confirm) {
                wx.openSetting();
              }
            }
          });
        } else {
          doExport();
        }
      },
      fail: function () {
        doExport();
      }
    });
  },

  // --- 点击历史场次，载入口令 ---
  viewHistorySession(e) {
    const token = e.currentTarget.dataset.token;
    const sid = e.currentTarget.dataset.sessionId;
    const lat = e.currentTarget.dataset.lat;
    const lng = e.currentTarget.dataset.lng;

    if (!token) {
      wx.showToast({ title: '该历史场次口令已失效或为空', icon: 'none' });
      return;
    }

    this.setData({
      qrToken: token,
      currentSessionId: sid || null,
      latitude: lat || null,
      longitude: lng || null
    });

    this.drawQRCode(token);

    wx.showToast({ title: '已载入场次口令', icon: 'none' });

    wx.pageScrollTo({
      scrollTop: 0,
      duration: 300
    });
  },

  // --- 教师手动结束签到 ---
  finalizeSession() {
    const that = this;
    const sessionId = this.data.currentSessionId;

    // [B3] 防重复点击
    if (this.data.finalizing) return;
    this.setData({ finalizing: true });

    if (!sessionId) {
      wx.showToast({ title: '未找到当前场次ID，请重新发起签到', icon: 'none' });
      this.setData({ finalizing: false });
      return;
    }

    wx.showModal({
      title: '结束签到确认',
      content: '确定要结束本次签到吗？\n\n结束后，未签到学生将被系统自动记为「缺勤」，且场次状态将变为「已关闭」。',
      confirmText: '确定结束',
      confirmColor: '#E74C3C',
      cancelText: '暂不结束',
      success(res) {
        if (!res.confirm) {
          that.setData({ finalizing: false });
          return;
        }

        wx.showLoading({ title: '正在结束...' });
        wx.request({
          url: config.API_BASE + '/api/sessions/' + sessionId + '/finalize',
          method: 'POST',
          header: { 'Content-Type': 'application/json' },
          success(finalizeRes) {
            wx.hideLoading();
            if (finalizeRes.data.code === 200) {
              const count = finalizeRes.data.data.absent_count || 0;
              wx.showToast({
                title: '已结束 · 缺勤补录 ' + count + ' 人',
                icon: 'success',
                duration: 2500
              });
              that.setData({
                finalizing: false,
                qrToken: '',
                currentSessionId: null,
                latitude: null,
                longitude: null
              });
              that.loadSessionHistory();
            } else {
              that.setData({ finalizing: false });
              wx.showToast({
                title: finalizeRes.data.message || '操作失败',
                icon: 'none'
              });
            }
          },
          fail() {
            wx.hideLoading();
            that.setData({ finalizing: false });
            wx.showToast({ title: '网络请求失败', icon: 'none' });
          }
        });
      }
    });
  }
});
