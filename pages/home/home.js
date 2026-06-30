const config = require('../../utils/config');

Page({
  data: {
    role: '',
    name: '',
    id: '',
    greeting: '',
    scanning: false
  },

  onShow() {
    const role = wx.getStorageSync('role') || '';
    const name = wx.getStorageSync('name') || '';
    const id = wx.getStorageSync('id') || '';

    let greeting = '';
    if (name) {
      if (role === 'student') {
        greeting = name + '同学，你好 👋';
      } else if (role === 'teacher') {
        greeting = name + '老师，您好 👋';
      } else {
        greeting = '你好，' + name;
      }
    } else {
      greeting = '欢迎使用课堂签到系统';
    }

    this.setData({ role, name, id, greeting });
  },

  // ===== 学生：扫一扫签到（完整链路） =====
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
            student_id: that.data.id,
            latitude: lat,
            longitude: lng
          },
          success(signRes) {
            wx.hideLoading();
            const d = signRes.data;

            if (d.code === 200) {
              const status = d.data.attendance_status;
              let statusText = '';
              let statusIcon = '';

              if (status === 'present') {
                statusText = '签到成功：已出勤';
                statusIcon = 'success';
              } else if (status === 'late') {
                statusText = '签到成功（迟到）';
                statusIcon = 'warn';
              } else {
                statusText = d.message || '签到失败';
                statusIcon = 'cancel';
              }

              // [B1] 释放扫码锁
              that.setData({ scanning: false });

              // 弹窗提示，引导查看记录
              wx.showModal({
                title: '签到结果',
                content: statusText + '\n\n可在「我的」页面查看签到记录',
                confirmText: '查看记录',
                cancelText: '好的',
                success: (modalRes) => {
                  if (modalRes.confirm) {
                    wx.switchTab({ url: '/pages/mine/mine' });
                  }
                }
              });
            } else {
              that.setData({ scanning: false });
              wx.showToast({ title: d.message || '签到失败', icon: 'none' });
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

  // ===== 教师：发起签到 =====
  handleTeacherAction() {
    wx.navigateTo({
      url: '/pages/teacher/teacher'
    });
  }
});
