-- ==========================================================================
--  答辩演示 - 种子数据集
--  使用方法：在 MySQL 中执行 SOURCE demo_data.sql;
--  前置条件：已执行 attendance_system.sql 创建数据库和表结构
-- ==========================================================================

USE attendance_system;

-- 如果 student 表缺少 gender 列则补上（admin_web 后台需要）
SET @col_exists = (SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA='attendance_system' AND TABLE_NAME='student' AND COLUMN_NAME='gender');
SET @sql = IF(@col_exists = 0, 'ALTER TABLE student ADD COLUMN gender VARCHAR(10) DEFAULT NULL COMMENT ''性别''', 'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- ============================
-- 1. 演示教师：张三 (T001)
-- ============================
INSERT INTO teacher (teacher_id, name, department) VALUES
('T001', '张三', '计算机学院')
ON DUPLICATE KEY UPDATE name=VALUES(name), department=VALUES(department);

-- ============================
-- 2. 两门课程
-- ============================
INSERT INTO course (course_id, course_name, department, credit) VALUES
('C001', '程序设计',   '计算机学院', 4),
('C002', '数据库原理', '计算机学院', 3)
ON DUPLICATE KEY UPDATE course_name=VALUES(course_name), department=VALUES(department), credit=VALUES(credit);

-- ============================
-- 3. 两个教学班
--    CL001: 程序设计, 20人(软件学院)
--    CL002: 数据库原理, 30人(计算机学院15人 + 大数据学院15人)
-- ============================
INSERT INTO teaching_class (class_id, semester, location, max_students, teacher_id, course_id) VALUES
('CL001', '2025-2026-2', '教3-101', 60, 'T001', 'C001'),
('CL002', '2025-2026-2', '教3-203', 60, 'T001', 'C002')
ON DUPLICATE KEY UPDATE semester=VALUES(semester), location=VALUES(location);

-- ============================
-- 4. 学生名单 (50人)
--    CL001 程序设计: 2025001-2025020, 软件学院
--    CL002 数据库原理: 2024001-2024030
--      2024001~2024015: 计算机学院
--      2024016~2024030: 大数据学院
-- ============================

-- CL001 程序设计班 —— 20人，软件学院
INSERT INTO student (student_id, name, gender, department, major, class_name) VALUES
('2025001', '王博文', '男', '软件学院', '软件工程', '软工2025-1班'),
('2025002', '李思雨', '女', '软件学院', '软件工程', '软工2025-1班'),
('2025003', '张浩然', '男', '软件学院', '软件工程', '软工2025-1班'),
('2025004', '刘雨桐', '女', '软件学院', '软件工程', '软工2025-1班'),
('2025005', '陈子轩', '男', '软件学院', '软件工程', '软工2025-1班'),
('2025006', '杨晓萌', '女', '软件学院', '软件工程', '软工2025-1班'),
('2025007', '赵文韬', '男', '软件学院', '软件工程', '软工2025-1班'),
('2025008', '黄诗涵', '女', '软件学院', '软件工程', '软工2025-1班'),
('2025009', '周明哲', '男', '软件学院', '软件工程', '软工2025-1班'),
('2025010', '吴雅琪', '女', '软件学院', '软件工程', '软工2025-1班'),
('2025011', '孙志远', '男', '软件学院', '软件工程', '软工2025-2班'),
('2025012', '马晓琳', '女', '软件学院', '软件工程', '软工2025-2班'),
('2025013', '朱俊杰', '男', '软件学院', '软件工程', '软工2025-2班'),
('2025014', '胡雨晴', '女', '软件学院', '软件工程', '软工2025-2班'),
('2025015', '林泽宇', '男', '软件学院', '软件工程', '软工2025-2班'),
('2025016', '何美玲', '女', '软件学院', '软件工程', '软工2025-2班'),
('2025017', '郭瑞峰', '男', '软件学院', '软件工程', '软工2025-2班'),
('2025018', '高雪莹', '女', '软件学院', '软件工程', '软工2025-2班'),
('2025019', '罗嘉豪', '男', '软件学院', '软件工程', '软工2025-2班'),
('2025020', '梁静怡', '女', '软件学院', '软件工程', '软工2025-2班')
ON DUPLICATE KEY UPDATE name=VALUES(name), gender=VALUES(gender), department=VALUES(department), major=VALUES(major), class_name=VALUES(class_name);

-- CL002 数据库原理班 —— 前15人 计算机学院
INSERT INTO student (student_id, name, gender, department, major, class_name) VALUES
('2024001', '陈志远', '男', '计算机学院', '计算机科学与技术', '计科2024-1班'),
('2024002', '林晓芳', '女', '计算机学院', '计算机科学与技术', '计科2024-1班'),
('2024003', '黄伟杰', '男', '计算机学院', '计算机科学与技术', '计科2024-1班'),
('2024004', '吴思颖', '女', '计算机学院', '计算机科学与技术', '计科2024-1班'),
('2024005', '郑浩宇', '男', '计算机学院', '计算机科学与技术', '计科2024-1班'),
('2024006', '许佳怡', '女', '计算机学院', '计算机科学与技术', '计科2024-2班'),
('2024007', '沈明辉', '男', '计算机学院', '计算机科学与技术', '计科2024-2班'),
('2024008', '丁雨萱', '女', '计算机学院', '计算机科学与技术', '计科2024-2班'),
('2024009', '谢文博', '男', '计算机学院', '计算机科学与技术', '计科2024-2班'),
('2024010', '范晓燕', '女', '计算机学院', '计算机科学与技术', '计科2024-2班'),
('2024011', '韩志豪', '男', '计算机学院', '计算机科学与技术', '计科2024-3班'),
('2024012', '唐梦琪', '女', '计算机学院', '计算机科学与技术', '计科2024-3班'),
('2024013', '冯峻熙', '男', '计算机学院', '计算机科学与技术', '计科2024-3班'),
('2024014', '曹思涵', '女', '计算机学院', '计算机科学与技术', '计科2024-3班'),
('2024015', '彭睿阳', '男', '计算机学院', '计算机科学与技术', '计科2024-3班'),

-- CL002 数据库原理班 —— 后15人 大数据学院
('2024016', '邓晓雯', '女', '大数据学院', '数据科学与大数据技术', '大数据2024-1班'),
('2024017', '蔡明哲', '男', '大数据学院', '数据科学与大数据技术', '大数据2024-1班'),
('2024018', '潘雨菲', '女', '大数据学院', '数据科学与大数据技术', '大数据2024-1班'),
('2024019', '田浩宇', '男', '大数据学院', '数据科学与大数据技术', '大数据2024-1班'),
('2024020', '余思琪', '女', '大数据学院', '数据科学与大数据技术', '大数据2024-1班'),
('2024021', '戴文轩', '男', '大数据学院', '数据科学与大数据技术', '大数据2024-2班'),
('2024022', '熊雨萌', '女', '大数据学院', '数据科学与大数据技术', '大数据2024-2班'),
('2024023', '谭骏豪', '男', '大数据学院', '数据科学与大数据技术', '大数据2024-2班'),
('2024024', '陆晓彤', '女', '大数据学院', '数据科学与大数据技术', '大数据2024-2班'),
('2024025', '廖俊熙', '男', '大数据学院', '数据科学与大数据技术', '大数据2024-2班'),
('2024026', '方雅琴', '女', '大数据学院', '数据科学与大数据技术', '大数据2024-3班'),
('2024027', '邹文斌', '男', '大数据学院', '数据科学与大数据技术', '大数据2024-3班'),
('2024028', '崔雨馨', '女', '大数据学院', '数据科学与大数据技术', '大数据2024-3班'),
('2024029', '龙一鸣', '男', '大数据学院', '数据科学与大数据技术', '大数据2024-3班'),
('2024030', '邱思敏', '女', '大数据学院', '数据科学与大数据技术', '大数据2024-3班')
ON DUPLICATE KEY UPDATE name=VALUES(name), gender=VALUES(gender), department=VALUES(department), major=VALUES(major), class_name=VALUES(class_name);

-- ============================
-- 5. 选课关系
-- ============================
-- CL001: 2025001-2025020 全部选修
INSERT INTO enrollment (student_id, class_id, enroll_date, enroll_status) VALUES
('2025001','CL001',CURRENT_DATE,'enrolled'),('2025002','CL001',CURRENT_DATE,'enrolled'),
('2025003','CL001',CURRENT_DATE,'enrolled'),('2025004','CL001',CURRENT_DATE,'enrolled'),
('2025005','CL001',CURRENT_DATE,'enrolled'),('2025006','CL001',CURRENT_DATE,'enrolled'),
('2025007','CL001',CURRENT_DATE,'enrolled'),('2025008','CL001',CURRENT_DATE,'enrolled'),
('2025009','CL001',CURRENT_DATE,'enrolled'),('2025010','CL001',CURRENT_DATE,'enrolled'),
('2025011','CL001',CURRENT_DATE,'enrolled'),('2025012','CL001',CURRENT_DATE,'enrolled'),
('2025013','CL001',CURRENT_DATE,'enrolled'),('2025014','CL001',CURRENT_DATE,'enrolled'),
('2025015','CL001',CURRENT_DATE,'enrolled'),('2025016','CL001',CURRENT_DATE,'enrolled'),
('2025017','CL001',CURRENT_DATE,'enrolled'),('2025018','CL001',CURRENT_DATE,'enrolled'),
('2025019','CL001',CURRENT_DATE,'enrolled'),('2025020','CL001',CURRENT_DATE,'enrolled')
ON DUPLICATE KEY UPDATE enroll_status='enrolled';

-- CL002: 2024001-2024030 全部选修
INSERT INTO enrollment (student_id, class_id, enroll_date, enroll_status) VALUES
('2024001','CL002',CURRENT_DATE,'enrolled'),('2024002','CL002',CURRENT_DATE,'enrolled'),
('2024003','CL002',CURRENT_DATE,'enrolled'),('2024004','CL002',CURRENT_DATE,'enrolled'),
('2024005','CL002',CURRENT_DATE,'enrolled'),('2024006','CL002',CURRENT_DATE,'enrolled'),
('2024007','CL002',CURRENT_DATE,'enrolled'),('2024008','CL002',CURRENT_DATE,'enrolled'),
('2024009','CL002',CURRENT_DATE,'enrolled'),('2024010','CL002',CURRENT_DATE,'enrolled'),
('2024011','CL002',CURRENT_DATE,'enrolled'),('2024012','CL002',CURRENT_DATE,'enrolled'),
('2024013','CL002',CURRENT_DATE,'enrolled'),('2024014','CL002',CURRENT_DATE,'enrolled'),
('2024015','CL002',CURRENT_DATE,'enrolled'),('2024016','CL002',CURRENT_DATE,'enrolled'),
('2024017','CL002',CURRENT_DATE,'enrolled'),('2024018','CL002',CURRENT_DATE,'enrolled'),
('2024019','CL002',CURRENT_DATE,'enrolled'),('2024020','CL002',CURRENT_DATE,'enrolled'),
('2024021','CL002',CURRENT_DATE,'enrolled'),('2024022','CL002',CURRENT_DATE,'enrolled'),
('2024023','CL002',CURRENT_DATE,'enrolled'),('2024024','CL002',CURRENT_DATE,'enrolled'),
('2024025','CL002',CURRENT_DATE,'enrolled'),('2024026','CL002',CURRENT_DATE,'enrolled'),
('2024027','CL002',CURRENT_DATE,'enrolled'),('2024028','CL002',CURRENT_DATE,'enrolled'),
('2024029','CL002',CURRENT_DATE,'enrolled'),('2024030','CL002',CURRENT_DATE,'enrolled')
ON DUPLICATE KEY UPDATE enroll_status='enrolled';

-- ============================
-- 6. 验证结果
-- ============================
SELECT '--- 教师 ---' AS info;
SELECT * FROM teacher WHERE teacher_id='T001';
SELECT '--- 课程 ---' AS info;
SELECT * FROM course;
SELECT '--- 教学班 ---' AS info;
SELECT * FROM teaching_class;
SELECT '--- 各班选课人数 ---' AS info;
SELECT class_id, COUNT(*) AS cnt FROM enrollment WHERE enroll_status='enrolled' GROUP BY class_id;
SELECT '--- 各院系学生人数 ---' AS info;
SELECT department, COUNT(*) AS cnt FROM student GROUP BY department;
