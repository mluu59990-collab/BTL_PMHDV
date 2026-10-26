-- Schema cms_logistics lấy từ MySQL thực tế; không chứa dữ liệu.

SET FOREIGN_KEY_CHECKS=0;

CREATE TABLE IF NOT EXISTS `chi_tiet_don_hang` (
  `ma` bigint NOT NULL AUTO_INCREMENT,
  `ma_don_hang` bigint NOT NULL,
  `ten_san_pham` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `so_luong` int NOT NULL,
  `ghi_chu` varchar(2000) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`ma`),
  KEY `ma_don_hang` (`ma_don_hang`),
  CONSTRAINT `chi_tiet_don_hang_ibfk_1` FOREIGN KEY (`ma_don_hang`) REFERENCES `don_hang` (`ma`),
  CONSTRAINT `chi_tiet_don_hang_chk_1` CHECK ((`so_luong` > 0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `chi_tiet_kien_hang` (
  `ma` bigint NOT NULL AUTO_INCREMENT,
  `ma_kien_hang` bigint NOT NULL,
  `ma_chi_tiet_don_hang` bigint NOT NULL,
  `so_luong` int NOT NULL,
  PRIMARY KEY (`ma`),
  UNIQUE KEY `uq_ctkh_kien_san_pham` (`ma_kien_hang`,`ma_chi_tiet_don_hang`),
  KEY `fk_ctkh_chi_tiet` (`ma_chi_tiet_don_hang`),
  CONSTRAINT `fk_ctkh_chi_tiet` FOREIGN KEY (`ma_chi_tiet_don_hang`) REFERENCES `chi_tiet_don_hang` (`ma`),
  CONSTRAINT `fk_ctkh_kien` FOREIGN KEY (`ma_kien_hang`) REFERENCES `kien_hang` (`ma`),
  CONSTRAINT `chi_tiet_kien_hang_chk_1` CHECK ((`so_luong` > 0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `don_hang` (
  `ma` bigint NOT NULL AUTO_INCREMENT,
  `ma_don` varchar(40) COLLATE utf8mb4_unicode_ci NOT NULL,
  `ma_khach_hang` bigint NOT NULL,
  `nguoi_tao` bigint NOT NULL,
  `ten_nguoi_nhan` varchar(150) COLLATE utf8mb4_unicode_ci NOT NULL,
  `sdt_nguoi_nhan` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `dia_chi_nguoi_nhan` varchar(500) COLLATE utf8mb4_unicode_ci NOT NULL,
  `phi_van_chuyen` decimal(18,2) NOT NULL DEFAULT '0.00',
  `trang_thai` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'PENDING',
  `ghi_chu` varchar(2000) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ngay_tao` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `ngay_cap_nhat` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`ma`),
  UNIQUE KEY `ma_don` (`ma_don`),
  KEY `ma_khach_hang` (`ma_khach_hang`),
  KEY `nguoi_tao` (`nguoi_tao`),
  KEY `ix_orders_status` (`trang_thai`),
  CONSTRAINT `don_hang_ibfk_1` FOREIGN KEY (`ma_khach_hang`) REFERENCES `khach_hang` (`ma`),
  CONSTRAINT `don_hang_ibfk_2` FOREIGN KEY (`nguoi_tao`) REFERENCES `nguoi_dung` (`ma`),
  CONSTRAINT `don_hang_chk_1` CHECK ((`phi_van_chuyen` >= 0)),
  CONSTRAINT `don_hang_chk_2` CHECK ((`trang_thai` in (_utf8mb4'PENDING',_utf8mb4'CONFIRMED',_utf8mb4'SHIPPING',_utf8mb4'DELIVERED',_utf8mb4'CANCELLED')))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `khach_hang` (
  `ma` bigint NOT NULL AUTO_INCREMENT,
  `ma_nguoi_dung` bigint DEFAULT NULL,
  `ten` varchar(150) COLLATE utf8mb4_unicode_ci NOT NULL,
  `so_dien_thoai` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `email` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `dia_chi` varchar(500) COLLATE utf8mb4_unicode_ci NOT NULL,
  `ma_nhan_vien_phu_trach` bigint DEFAULT NULL,
  `dang_hoat_dong` tinyint(1) NOT NULL DEFAULT '1',
  `ngay_tao` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `ngay_cap_nhat` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`ma`),
  UNIQUE KEY `ma_nguoi_dung` (`ma_nguoi_dung`),
  KEY `ma_nhan_vien_phu_trach` (`ma_nhan_vien_phu_trach`),
  CONSTRAINT `khach_hang_ibfk_1` FOREIGN KEY (`ma_nguoi_dung`) REFERENCES `nguoi_dung` (`ma`),
  CONSTRAINT `khach_hang_ibfk_2` FOREIGN KEY (`ma_nhan_vien_phu_trach`) REFERENCES `nguoi_dung` (`ma`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `kho_hang` (
  `ma` bigint NOT NULL AUTO_INCREMENT,
  `ma_kho` varchar(30) COLLATE utf8mb4_unicode_ci NOT NULL,
  `ten` varchar(150) COLLATE utf8mb4_unicode_ci NOT NULL,
  `dia_chi` varchar(500) COLLATE utf8mb4_unicode_ci NOT NULL,
  `ma_quoc_gia` varchar(2) COLLATE utf8mb4_unicode_ci NOT NULL,
  `dang_hoat_dong` tinyint(1) NOT NULL DEFAULT '1',
  PRIMARY KEY (`ma`),
  UNIQUE KEY `ma_kho` (`ma_kho`),
  CONSTRAINT `kho_hang_chk_1` CHECK ((`ma_quoc_gia` in (_utf8mb4'CN',_utf8mb4'VN')))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `kien_hang` (
  `ma` bigint NOT NULL AUTO_INCREMENT,
  `ma_don_hang` bigint NOT NULL,
  `ma_van_don` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `ma_kho_hang` bigint DEFAULT NULL,
  `khoi_luong_kg` decimal(12,3) NOT NULL,
  `chieu_dai_cm` decimal(10,2) NOT NULL,
  `chieu_rong_cm` decimal(10,2) NOT NULL,
  `chieu_cao_cm` decimal(10,2) NOT NULL,
  `trang_thai` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'CREATED',
  `ngay_tao` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `ngay_cap_nhat` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`ma`),
  UNIQUE KEY `ma_van_don` (`ma_van_don`),
  KEY `ma_don_hang` (`ma_don_hang`),
  KEY `ma_kho_hang` (`ma_kho_hang`),
  CONSTRAINT `kien_hang_ibfk_1` FOREIGN KEY (`ma_don_hang`) REFERENCES `don_hang` (`ma`),
  CONSTRAINT `kien_hang_ibfk_2` FOREIGN KEY (`ma_kho_hang`) REFERENCES `kho_hang` (`ma`),
  CONSTRAINT `kien_hang_chk_1` CHECK ((`khoi_luong_kg` > 0)),
  CONSTRAINT `kien_hang_chk_2` CHECK ((`chieu_dai_cm` > 0)),
  CONSTRAINT `kien_hang_chk_3` CHECK ((`chieu_rong_cm` > 0)),
  CONSTRAINT `kien_hang_chk_4` CHECK ((`chieu_cao_cm` > 0)),
  CONSTRAINT `kien_hang_chk_5` CHECK ((`trang_thai` in (_utf8mb4'CREATED',_utf8mb4'IN_WAREHOUSE',_utf8mb4'IN_TRANSIT',_utf8mb4'DELIVERED',_utf8mb4'CANCELLED'))),
  CONSTRAINT `kien_hang_chk_6` CHECK ((((`trang_thai` = _utf8mb4'IN_WAREHOUSE') and (`ma_kho_hang` is not null)) or ((`trang_thai` <> _utf8mb4'IN_WAREHOUSE') and (`ma_kho_hang` is null))))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `lich_su_van_chuyen` (
  `ma` bigint NOT NULL AUTO_INCREMENT,
  `ma_kien_hang` bigint NOT NULL,
  `ma_kho_hang` bigint DEFAULT NULL,
  `trang_thai` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `ghi_chu` varchar(2000) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `nguoi_tao` bigint NOT NULL,
  `ngay_tao` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`ma`),
  KEY `ma_kho_hang` (`ma_kho_hang`),
  KEY `nguoi_tao` (`nguoi_tao`),
  KEY `ix_tracking_events_time` (`ma_kien_hang`,`ngay_tao`,`ma`),
  CONSTRAINT `lich_su_van_chuyen_ibfk_1` FOREIGN KEY (`ma_kien_hang`) REFERENCES `kien_hang` (`ma`),
  CONSTRAINT `lich_su_van_chuyen_ibfk_2` FOREIGN KEY (`ma_kho_hang`) REFERENCES `kho_hang` (`ma`),
  CONSTRAINT `lich_su_van_chuyen_ibfk_3` FOREIGN KEY (`nguoi_tao`) REFERENCES `nguoi_dung` (`ma`),
  CONSTRAINT `lich_su_van_chuyen_chk_1` CHECK ((`trang_thai` in (_utf8mb4'CREATED',_utf8mb4'IN_WAREHOUSE',_utf8mb4'IN_TRANSIT',_utf8mb4'DELIVERED',_utf8mb4'CANCELLED')))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `ma_lam_moi` (
  `ma` bigint NOT NULL AUTO_INCREMENT,
  `ma_nguoi_dung` bigint NOT NULL,
  `ma_dinh_danh_token` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `ngay_het_han` datetime(6) NOT NULL,
  `ngay_thu_hoi` datetime(6) DEFAULT NULL,
  `ngay_tao` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`ma`),
  UNIQUE KEY `ma_dinh_danh_token` (`ma_dinh_danh_token`),
  KEY `ma_nguoi_dung` (`ma_nguoi_dung`),
  CONSTRAINT `ma_lam_moi_ibfk_1` FOREIGN KEY (`ma_nguoi_dung`) REFERENCES `nguoi_dung` (`ma`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `nguoi_dung` (
  `ma` bigint NOT NULL AUTO_INCREMENT,
  `ten_dang_nhap` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `email` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ho_ten` varchar(150) COLLATE utf8mb4_unicode_ci NOT NULL,
  `so_dien_thoai` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `mat_khau_bam` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `vai_tro` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `trang_thai` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'ACTIVE',
  `lan_dang_nhap_cuoi` datetime(6) DEFAULT NULL,
  `ngay_tao` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `ngay_cap_nhat` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`ma`),
  UNIQUE KEY `ten_dang_nhap` (`ten_dang_nhap`),
  UNIQUE KEY `email` (`email`),
  CONSTRAINT `nguoi_dung_chk_1` CHECK ((`vai_tro` in (_utf8mb4'ADMIN',_utf8mb4'SALE',_utf8mb4'WAREHOUSE',_utf8mb4'ACCOUNTANT',_utf8mb4'CUSTOMER'))),
  CONSTRAINT `nguoi_dung_chk_2` CHECK ((`trang_thai` in (_utf8mb4'ACTIVE',_utf8mb4'INACTIVE',_utf8mb4'LOCKED')))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `thanh_toan` (
  `ma` bigint NOT NULL AUTO_INCREMENT,
  `ma_don_hang` bigint NOT NULL,
  `so_tien` decimal(18,2) NOT NULL,
  `loai_giao_dich` varchar(10) COLLATE utf8mb4_unicode_ci NOT NULL,
  `phuong_thuc` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `ma_tham_chieu` varchar(80) COLLATE utf8mb4_unicode_ci NOT NULL,
  `nguoi_tao` bigint NOT NULL,
  `ngay_tao` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`ma`),
  UNIQUE KEY `ma_tham_chieu` (`ma_tham_chieu`),
  KEY `ma_don_hang` (`ma_don_hang`),
  KEY `nguoi_tao` (`nguoi_tao`),
  CONSTRAINT `thanh_toan_ibfk_1` FOREIGN KEY (`ma_don_hang`) REFERENCES `don_hang` (`ma`),
  CONSTRAINT `thanh_toan_ibfk_2` FOREIGN KEY (`nguoi_tao`) REFERENCES `nguoi_dung` (`ma`),
  CONSTRAINT `thanh_toan_chk_1` CHECK ((`so_tien` > 0)),
  CONSTRAINT `thanh_toan_chk_2` CHECK ((`loai_giao_dich` in (_utf8mb4'PAYMENT',_utf8mb4'REFUND'))),
  CONSTRAINT `thanh_toan_chk_3` CHECK ((`phuong_thuc` in (_utf8mb4'CASH',_utf8mb4'BANK_TRANSFER')))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SET FOREIGN_KEY_CHECKS=1;
