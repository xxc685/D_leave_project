// pages/stats/stats.js
const { STAT_API } = require('../../utils/config');

Page({
  data: {
    role: '',
    name: '',
    // ===== 学生端数据 =====
    studentSummary: { attendance_rate: 0, total_sessions: 0, leave_count: 0 },
    studentCourseStats: [],
    studentAbsentList: [],
    studentRecords: [],
    // ===== 教师端数据 =====
    teacherClasses: [],
    selectedClassIndex: 0,
    selectedClassDetail: null,
    // ===== 通用 =====
    loading: false
  },

  onLoad(options) {
    const role = options.role || wx.getStorageSync('role') || '';
    const name = wx.getStorageSync('name') || '';
    this.setData({ role, name });

    if (role === 'student') {
      this.loadStudentStats();
    } else if (role === 'teacher') {
      this.loadTeacherStats();
    } else {
      wx.showToast({ title: '请先登录', icon: 'none' });
    }
  },

  // ===== 学生端：加载个人出勤统计 =====
  async loadStudentStats() {
    const studentId = wx.getStorageSync('id');
    if (!studentId) {
      wx.showToast({ title: '未获取到学号', icon: 'none' });
      return;
    }
    this.setData({ loading: true });
    try {
      // 1. 获取汇总
      const sumRes = await this.request(STAT_API + '/api/statistics/student/' + studentId);
      if (sumRes.code === 200) {
        this.setData({ 'studentSummary': sumRes.data });
      }
      // 2. 获取明细记录
      const recRes = await this.request(STAT_API + '/api/statistics/student/' + studentId + '/records');
      if (recRes.code === 200) {
        const records = recRes.data || [];
        // 同一场次可能保留多次无效尝试，只取最终有效状态参与统计
        const priority = { leave: 5, present: 4, late: 3, absent: 2, invalid: 1 };
        const sessionMap = new Map();
        records.forEach(r => {
          const key = r.session_id != null ? String(r.session_id) : 'record-' + r.record_id;
          const current = sessionMap.get(key);
          if (!current || (priority[r.attendance_status] || 0) > (priority[current.attendance_status] || 0)) {
            sessionMap.set(key, r);
          }
        });
        const effectiveRecords = Array.from(sessionMap.values());

        // 按课程分组
        const courseMap = new Map();
        const absentList = [];
        effectiveRecords.forEach(r => {
          const course = r.course_name || '未知课程';
          if (!courseMap.has(course)) {
            courseMap.set(course, { total: 0, valid: 0, absent: 0, leave: 0 });
          }
          const stat = courseMap.get(course);
          if (r.attendance_status === 'leave') {
            stat.leave += 1;
          } else {
            stat.total += 1;
            if (r.attendance_status === 'present' || r.attendance_status === 'late') {
              stat.valid += 1;
            } else if (r.attendance_status === 'absent') {
              stat.absent += 1;
              absentList.push({
                course_name: course,
                session_date: r.session_date || (r.scan_time ? r.scan_time.slice(0,10) : '')
              });
            }
          }
        });
        const stats = [];
        courseMap.forEach((value, key) => {
          stats.push({
            course_name: key,
            total: value.total,
            valid: value.valid,
            absent: value.absent,
            leave: value.leave,
            rate: value.total ? Math.round((value.valid / value.total) * 100) : 0
          });
        });
        stats.sort((a, b) => a.course_name.localeCompare(b.course_name));
        this.setData({
          studentRecords: records,
          studentCourseStats: stats,
          studentAbsentList: absentList
        });
      }
    } catch (e) {
      console.error('加载学生统计失败', e);
      wx.showToast({ title: '加载失败，请重试', icon: 'none' });
    } finally {
      this.setData({ loading: false });
    }
  },

  // ===== 教师端：加载所带班级的出勤统计 =====
  async loadTeacherStats() {
    const teacherId = wx.getStorageSync('id');
    if (!teacherId) {
      wx.showToast({ title: '未获取到工号', icon: 'none' });
      return;
    }
    this.setData({ loading: true });
    try {
      // 1. 获取教师汇总
      const sumRes = await this.request(STAT_API + '/api/statistics/teacher/' + teacherId + '/summary');
      if (sumRes.code === 200) {
        const data = sumRes.data;
        const classList = data.class_list || [];
        // 2. 为每个班级加载缺勤学生列表
        const enrichedClasses = [];
        for (let cls of classList) {
          const classId = cls.class_id;
          const absentRes = await this.request(STAT_API + '/api/statistics/class/' + classId + '/absent_students');
          const absentStudents = (absentRes.code === 200) ? (absentRes.data || []) : [];
          enrichedClasses.push({
            ...cls,
            absentStudents: absentStudents
          });
        }
        this.setData({
          teacherClasses: enrichedClasses,
          selectedClassIndex: 0,
          selectedClassDetail: enrichedClasses.length > 0 ? enrichedClasses[0] : null
        });
      } else {
        wx.showToast({ title: '获取教师数据失败', icon: 'none' });
      }
    } catch (e) {
      console.error('加载教师统计失败', e);
      wx.showToast({ title: '加载失败，请重试', icon: 'none' });
    } finally {
      this.setData({ loading: false });
    }
  },

  // ===== 教师端：切换班级 =====
  onClassChange(e) {
    const index = e.detail.value;
    this.setData({
      selectedClassIndex: index,
      selectedClassDetail: this.data.teacherClasses[index] || null
    });
  },

  // ===== 通用请求封装 =====
  request(url) {
    return new Promise((resolve, reject) => {
      wx.request({
        url: url,
        method: 'GET',
        success: res => {
          if (res.statusCode === 200) {
            resolve(res.data);
          } else {
            reject(new Error('HTTP ' + res.statusCode));
          }
        },
        fail: reject
      });
    });
  },

  // ===== 下拉刷新 =====
  onPullDownRefresh() {
    const role = this.data.role;
    if (role === 'student') this.loadStudentStats();
    else if (role === 'teacher') this.loadTeacherStats();
    wx.stopPullDownRefresh();
  },

  // ===== 手动刷新 =====
  handleRefresh() {
    const role = this.data.role;
    if (role === 'student') this.loadStudentStats();
    else if (role === 'teacher') this.loadTeacherStats();
  }
});