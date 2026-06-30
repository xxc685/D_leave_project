SELECT 
    s.student_id,
    s.name,
    s.department,
    COUNT(ar.record_id) AS total_sessions,
    SUM(CASE WHEN ar.attendance_status = 'present' THEN 1 ELSE 0 END) AS present_count,
    SUM(CASE WHEN ar.attendance_status = 'late' THEN 1 ELSE 0 END) AS late_count,
    SUM(CASE WHEN ar.attendance_status = 'absent' THEN 1 ELSE 0 END) AS absent_count,
    ROUND(
        (SUM(CASE WHEN ar.attendance_status IN ('present','late') THEN 1 ELSE 0 END) 
        / COUNT(ar.record_id)) * 100,2
    ) AS attendance_rate
FROM student s
LEFT JOIN attendance_record ar ON s.student_id = ar.student_id
WHERE s.student_id = '学号id'
GROUP BY s.student_id, s.name, s.department;