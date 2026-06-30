Page({
  data: {
    role: '',
    name: '',
    id: '',
    roleLabel: '',
    menuLabel: '签到记录'
  },

  onShow() {
    const role = wx.getStorageSync('role') || '';
    const name = wx.getStorageSync('name') || '';
    const id = wx.getStorageSync('id') || '';

    let roleLabel = '';
    let menuLabel = '签到记录';
    if (role === 'student') {
      roleLabel = '学生';
      menuLabel = '我的签到历史';
    } else if (role === 'teacher') {
      roleLabel = '教师';
      menuLabel = '我发起的签到';
    }

    this.setData({ role, name, id, roleLabel, menuLabel });
  },

  // --- 跳转统计看板 ---
  goToStats() {
    const role = wx.getStorageSync('role') || '';
    wx.navigateTo({ 
      url: '/pages/stats/stats?role=' + role 
    });
  },
  
  // --- 退出登录 ---
  handleLogout() {
    wx.showModal({
      title: '退出确认',
      content: '确定要退出登录吗？',
      confirmColor: '#E74C3C',
      success: (res) => {
        if (res.confirm) {
          wx.clearStorageSync();
          wx.reLaunch({ url: '/pages/login/login' });
        }
      }
    });
  },

  // --- 跳转历史记录 ---
  goToHistory() {
    if (this.data.role === 'student') {
      wx.navigateTo({ url: '/pages/student/student' });
    } else if (this.data.role === 'teacher') {
      wx.navigateTo({ url: '/pages/teacher/teacher' });
    }
  }
});
