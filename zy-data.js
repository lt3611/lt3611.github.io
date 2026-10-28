// ==========================================
// 配置文件（以后只需要改这个文件，网页刷新就生效）
// ==========================================
window.NAV_CONFIG = {
  // 主页地址
  home: "https://lt3611.ccwu.cc/",
  
  // 按钮数据
  rows: [
    // 第 1 排 (右列复制)
    { 
      leftText: "日历", leftUrl: "https://lt3611.ccwu.cc/tools/tq.html", 
      middleText: "路由", middleUrl: "http://192.168.50.1", 
      rightText: "常用接口", rightUrl: "https://lt3611.ccwu.cc/tools/tv.txt", rightType: "copy" 
    },
    // 第 2 排 (右列复制)
    { 
      leftText: "A3转A4", leftUrl: "/tools/pdf.html", 
      middleText: "路由查看", middleUrl: "http://192.168.50.1:9990/ui/zashboard/#/setup?hostname=192.168.50.1&port=9990&secret=clash", 
      rightText: "电视导航", rightUrl: "https://lt3611.ccwu.cc/tools/tv3.txt", rightType: "copy" 
    },
    // 第 3 排 (右列复制)
    { 
      leftText: "52pojie", leftUrl: "https://www.52pojie.cn/forum.php?mod=forumdisplay&fid=16&filter=typeid&typeid=232", 
      middleText: "电视", middleUrl: "https://lt3611.ccwu.cc", 
      rightText: "学习导航", rightUrl: "https://lt3611.ccwu.cc/tools/tv1.txt", rightType: "copy" 
    },
    
    // ==========================================
    // ⬇️ 下面是第 4、5、6 排，右列全部是跳转链接 (rightType: "link") ⬇️
    // ==========================================
    
    // 第 4 排 (右列跳转)
    { 
      leftText: "自用网盘", leftUrl: "https://wwbhy.lanzoum.com/b031oq4qf", 
      middleText: "备用网址1", middleUrl: "#", 
      rightText: "常用链接1", rightUrl: "https://lt3611.ccwu.cc/tools/tv4.txt", rightType: "link" 
    },
    // 第 5 排 (右列跳转)
    { 
      leftText: "备用工具2", leftUrl: "#", 
      middleText: "网址2", middleUrl: "#", 
      rightText: "链接2", rightUrl: "https://example.com", rightType: "link" 
    },
    // 第 6 排 (右列跳转)
    { 
      leftText: "备用工具3", leftUrl: "#", 
      middleText: "网址3", middleUrl: "#", 
      rightText: "链接3", rightUrl: "https://example.com", rightType: "link" 
    }
  ]
};