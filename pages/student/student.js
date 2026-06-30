const config = require('../../utils/config');

// ===== [T7] WXS 状态映射（WXS 不可用时的 JS 降级） =====
var STATUS_MAP = {
  present: { label: '出勤', cls: 'tag-present' },
  late:    { label: '迟到', cls: 'tag-late' },
  absent:  { label: '缺勤', cls: 'tag-absent' },
  invalid: { label: '无效', cls: 'tag-invalid' },
  leave:   { label: '请假', cls: 'tag-leave' }
};

Page({
  data: {
    // 对应 STUDENT 表字段
    studentName: '',
    studentId: '',

    // 页面状态展示
    attendanceStatus: '',
    statusClass: '',
    statusIcon: '',
    scanTime: '',
    locationStatus: '',

    // 防重复点击
    scanning: false,

    // [T7] 签到历史
    historyList: [],
    historyLoading: false,

    // 请假申请
    leaveOptions: [],
    leaveIndex: 0,
    leaveReason: '',
    leaveRequests: [],
    leaveLoading: false,
    leaveSubmitting: false
  },

  onLoad() {
    // 从全局缓存读取登录身份
    const id = wx.getStorageSync('id');
    const name = wx.getStorageSync('name');
    if (id) {
      this.setData({
        studentId: id,
        studentName: name || ''
      });
      // [T7] 自动拉取历史
      this.loadHistory();
      this.loadLeaveData();
    }
  },

  // --- 核心：扫码 → 定位 → 签到 ---
  handleScan() {
    // [B1] 防重复点击
    if (this.data.scanning) return;
    this.setData({ scanning: true });

    wx.scanCode({
      onlyFromCamera: false,
      success: (scanRes) => {
        const qrToken = (scanRes.result || '').trim();
        if (!qrToken) {
          wx.showToast({ title: '二维码内容为空', icon: 'none' });
          this.setData({ scanning: false });
          return;
        }
        this.fetchLocationAndSignIn(qrToken);
      },
      fail: (err) => {
        this.setData({ scanning: false });
        if (err.errMsg && err.errMsg.indexOf('cancel') !== -1) return;
        wx.showToast({ title: '扫码失败，请重试', icon: 'none' });
      }
    });
  },

  /** 扫码成功后获取真实定位，再提交签到 */
  fetchLocationAndSignIn(qrToken) {
    wx.showLoading({ title: '正在获取定位...' });
    wx.getLocation({
      type: 'gcj02',
      isHighAccuracy: true,
      highAccuracyExpireTime: 5000,
      success: (loc) => {
        wx.hideLoading();
        this.processCheckIn(qrToken, loc.latitude, loc.longitude);
      },
      fail: (err) => {
        wx.hideLoading();
        const denied = err.errMsg &&
          (err.errMsg.indexOf('auth deny') !== -1 ||
           err.errMsg.indexOf('authorize') !== -1 ||
           err.errMsg.indexOf('permission') !== -1);
        if (denied) {
          wx.showModal({
            title: '定位权限未开启',
            content: '必须开启定位权限才能完成签到，请在设置中允许使用位置信息。',
            confirmText: '去设置',
            cancelText: '取消',
            success: (res) => {
              if (res.confirm) {
                wx.openSetting({
                  success: (settingRes) => {
                    if (settingRes.authSetting['scope.userLocation']) {
                      wx.showToast({ title: '已授权，请重新扫码', icon: 'none' });
                    }
                  }
                });
              }
            }
          });
        } else {
          wx.showModal({
            title: '定位获取失败',
            content: err.errMsg || '无法获取当前位置，请检查 GPS 或网络后重试。',
            showCancel: false
          });
        }
      }
    });
  },

  /** 校验 token 并调用 POST /api/sign_in */
  processCheckIn(qrToken, lat, lng) {
    var that = this;
    wx.showLoading({ title: '正在校验场次...' });

    wx.request({
      url: config.API_BASE + '/api/sessions/by_token/' + qrToken,
      method: 'GET',
      success(res) {
        if (res.data.code !== 200) {
          wx.hideLoading();
          that.setData({ scanning: false });
          wx.showToast({ title: res.data.message || '二维码无效', icon: 'none' });
          return;
        }

        wx.showLoading({ title: '正在提交签到...' });
        wx.request({
          url: config.API_BASE + '/api/sign_in',
          method: 'POST',
          header: { 'Content-Type': 'application/json' },
          data: {
            qr_token: qrToken,
            student_id: that.data.studentId,
            latitude: lat,
            longitude: lng
          },
          success(signRes) {
            wx.hideLoading();
            const d = signRes.data;

            if (d.code === 200) {
              const status = d.data.attendance_status;
              let statusText = '';
              let statusClass = '';
              let statusIcon = '';
              let locationStatus = '';

              if (status === 'present') {
                statusText = '签到成功：已出勤';
                statusClass = 'status-success';
                statusIcon = 'success';
              } else if (status === 'late') {
                statusText = '签到成功（迟到）';
                statusClass = 'status-late';
                statusIcon = 'warn';
              } else {
                statusText = d.message || '签到失败';
                statusClass = 'status-fail';
                statusIcon = 'cancel';
              }

              if (d.data.distance_m != null) {
                locationStatus = '定位距离：' + d.data.distance_m + ' 米';
              } else {
                locationStatus = '定位：' + lat.toFixed(6) + ', ' + lng.toFixed(6);
              }

              that.setData({
                attendanceStatus: statusText,
                statusClass,
                statusIcon,
                scanTime: d.data.scan_time || '',
                locationStatus
              });

              // [B1] 释放扫码锁
              that.setData({ scanning: false });
              // [T7] 签到成功后自动刷新历史
              that.loadHistory();
            } else {
              that.setData({
                scanning: false,
                attendanceStatus: d.message || '签到失败',
                statusClass: 'status-fail',
                statusIcon: 'cancel',
                scanTime: '',
                locationStatus: ''
              });
            }
          },
          fail() {
            wx.hideLoading();
            that.setData({ scanning: false });
            wx.showToast({ title: '网络请求失败，请重试', icon: 'none' });
          }
        });
      },
      fail() {
        wx.hideLoading();
        that.setData({ scanning: false });
        wx.showToast({ title: '网络请求失败，请重试', icon: 'none' });
      }
    });
  },

  // ===== 请假申请 =====
  requestApi(url, method, data) {
    return new Promise((resolve, reject) => {
      wx.request({
        url,
        method: method || 'GET',
        header: { 'Content-Type': 'application/json' },
        data: data || {},
        success: res => resolve(res.data),
        fail: reject
      });
    });
  },

  async loadLeaveData(showToast) {
    const studentId = this.data.studentId;
    if (!studentId || this.data.leaveLoading) return;
    this.setData({ leaveLoading: true });
    try {
      const results = await Promise.all([
        this.requestApi(config.API_BASE + '/api/students/' + studentId + '/leave_options'),
        this.requestApi(config.API_BASE + '/api/students/' + studentId + '/leave_requests')
      ]);
      const optionRes = results[0];
      const requestRes = results[1];
      if (optionRes.code !== 200) throw new Error(optionRes.message || '请假场次加载失败');
      if (requestRes.code !== 200) throw new Error(requestRes.message || '请假记录加载失败');

      const leaveOptions = (optionRes.data || []).map(item => ({
        ...item,
        label: (item.course_name || '未知课程') + ' · ' + item.session_date +
          ' · 场次#' + item.session_id + (item.leave_status === 'rejected' ? '（可重新申请）' : '')
      }));
      const statusMap = {
        pending: { label: '待审批', cls: 'leave-pending' },
        approved: { label: '已批准', cls: 'leave-approved' },
        rejected: { label: '已驳回', cls: 'leave-rejected' }
      };
      const leaveRequests = (requestRes.data || []).map(item => {
        const state = statusMap[item.status] || { label: item.status, cls: 'leave-pending' };
        return { ...item, status_label: state.label, status_cls: state.cls };
      });
      this.setData({
        leaveOptions,
        leaveRequests,
        leaveIndex: leaveOptions.length ? Math.min(this.data.leaveIndex, leaveOptions.length - 1) : 0
      });
      if (showToast) wx.showToast({ title: '请假数据已刷新', icon: 'success' });
    } catch (err) {
      wx.showToast({ title: err.message || '请假数据加载失败', icon: 'none' });
    } finally {
      this.setData({ leaveLoading: false });
    }
  },

  bindLeaveSessionChange(e) {
    this.setData({ leaveIndex: Number(e.detail.value) });
  },

  inputLeaveReason(e) {
    this.setData({ leaveReason: e.detail.value });
  },

  async submitLeaveRequest() {
    if (this.data.leaveSubmitting) return;
    const option = this.data.leaveOptions[this.data.leaveIndex];
    const reason = (this.data.leaveReason || '').trim();
    if (!option) {
      wx.showToast({ title: '当前没有可申请请假的场次', icon: 'none' });
      return;
    }
    if (!reason) {
      wx.showToast({ title: '请填写请假原因', icon: 'none' });
      return;
    }
    this.setData({ leaveSubmitting: true });
    try {
      const res = await this.requestApi(config.API_BASE + '/api/leave_requests', 'POST', {
        student_id: this.data.studentId,
        session_id: option.session_id,
        reason
      });
      if (res.code !== 200) throw new Error(res.message || '提交失败');
      wx.showToast({ title: '请假申请已提交', icon: 'success' });
      this.setData({ leaveReason: '', leaveIndex: 0 });
      await this.loadLeaveData();
    } catch (err) {
      wx.showToast({ title: err.message || '提交失败', icon: 'none' });
    } finally {
      this.setData({ leaveSubmitting: false });
    }
  },

  refreshLeaveData() {
    this.loadLeaveData(true);
  },

  // ===== [T7] 加载我的签到历史 =====
  loadHistory(showToast) {
    const studentId = this.data.studentId;
    if (!studentId) return;

    this.setData({ historyLoading: true });

    var that = this;
    wx.request({
      url: config.API_BASE + '/api/students/' + studentId + '/records',
      method: 'GET',
      success: function (res) {
        if (res.data.code === 200) {
          var list = (res.data.data || []).map(function (item) {
            var st = STATUS_MAP[item.attendance_status];
            return {
              record_id: item.record_id,
              session_id: item.session_id,
              course_name: item.course_name || '未知课程',
              session_date: item.session_date || '',
              scan_time: item.scan_time || '—',
              attendance_status: item.attendance_status,
              status_label: st ? st.label : item.attendance_status,
              status_cls: st ? st.cls : 'tag-invalid',
              is_valid: item.is_valid,
              remark: item.remark || ''
            };
          });
          that.setData({ historyList: list });
          // [B4] 只在手动刷新时提示
          if (showToast) {
            wx.showToast({ title: '已刷新', icon: 'success', duration: 1000 });
          }
        } else {
          wx.showToast({ title: res.data.message || '历史加载失败', icon: 'none' });
          that.setData({ historyList: [] });
        }
      },
      fail: function () {
        wx.showToast({ title: '网络请求失败', icon: 'none' });
        that.setData({ historyList: [] });
      },
      complete: function () {
        that.setData({ historyLoading: false });
      }
    });
  },

  // [T7] 手动刷新历史按钮
  onRefreshHistory() {
    if (this.data.historyLoading) return;
    this.loadHistory(true);
  }
});
