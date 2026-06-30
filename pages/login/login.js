Page({
  data: {
    role: 'student',       // 'student' | 'teacher'
    student_id: '',
    teacher_id: '',
    name: ''
  },

  // --- 切换身份 Tab ---
  switchRole(e) {
    const role = e.currentTarget.dataset.role;
    this.setData({ role });
  },

  // --- 输入绑定 ---
  onInputStudentId(e) {
    this.setData({ student_id: e.detail.value });
  },
  onInputTeacherId(e) {
    this.setData({ teacher_id: e.detail.value });
  },
  onInputName(e) {
    this.setData({ name: e.detail.value });
  },

  // --- 登录 ---
  handleLogin() {
    const { role, student_id, teacher_id, name } = this.data;

    // 校验
    if (!name.trim()) {
      wx.showToast({ title: '请输入姓名', icon: 'none' });
      return;
    }

    if (role === 'student') {
      if (!student_id.trim()) {
        wx.showToast({ title: '请输入学号', icon: 'none' });
        return;
      }
      // 存入本地缓存
      wx.setStorageSync('role', 'student');
      wx.setStorageSync('id', student_id.trim());
      wx.setStorageSync('name', name.trim());
    } else {
      if (!teacher_id.trim()) {
        wx.showToast({ title: '请输入工号', icon: 'none' });
        return;
      }
      wx.setStorageSync('role', 'teacher');
      wx.setStorageSync('id', teacher_id.trim());
      wx.setStorageSync('name', name.trim());
    }

    wx.showToast({ title: '登录成功', icon: 'success', duration: 1200 });

    setTimeout(() => {
      wx.switchTab({ url: '/pages/home/home' });
    }, 1200);
  }
});
