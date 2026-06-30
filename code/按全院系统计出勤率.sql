SELECT 
    s.department,
    COUNT(DISTINCT s.student_id) AS student_count,
    ROUND(
        AVG(CASE WHEN ar.attendance_status IN ('present','late') THEN 1 ELSE 0 END)*100,2
    ) AS avg_attendance_rate
FROM student s
LEFT JOIN attendance_record ar ON s.student_id = ar.student_id
GROUP BY s.department;