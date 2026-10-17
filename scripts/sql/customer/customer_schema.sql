-- 客户研判模块 5 张业务表（参考 DDL，与 app/models/customer 对应）
-- 公共库 stuproject；字符集 utf8mb4。共享表 user_account / employee / org_department
-- / customer_profile 由对应模块维护，此处不重复建表。

CREATE TABLE IF NOT EXISTS product (
    id                      BIGINT NOT NULL AUTO_INCREMENT,
    product_code            VARCHAR(32)  NOT NULL COMMENT '产品编码，创建后不可修改',
    product_name            VARCHAR(100) NOT NULL,
    description             TEXT         NULL,
    target_profile_summary  TEXT         NULL,
    status                  VARCHAR(32)  NOT NULL DEFAULT 'active' COMMENT 'active/disabled',
    row_version             INT          NOT NULL DEFAULT 1,
    created_at              DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at              DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_product_code (product_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS customer_source (
    id                      BIGINT NOT NULL AUTO_INCREMENT,
    source_type             VARCHAR(16)  NOT NULL COMMENT 'text/pdf/excel',
    raw_content             TEXT         NULL COMMENT '受控原始文本，默认不返回',
    file_name               VARCHAR(255) NULL,
    file_path               VARCHAR(255) NULL COMMENT '非公网受控定位键',
    status                  VARCHAR(32)  NOT NULL DEFAULT 'pending' COMMENT 'pending/parsed/failed',
    created_by              BIGINT       NULL COMMENT '提交账号 user_id',
    row_version             INT          NOT NULL DEFAULT 1,
    current_parse_batch_id  BIGINT       NULL,
    created_at              DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at              DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS customer_info (
    id                  BIGINT NOT NULL AUTO_INCREMENT,
    source_id           BIGINT       NOT NULL,
    parse_batch_id      BIGINT       NULL,
    source_row_key      VARCHAR(128) NULL COMMENT '来源内稳定行键',
    customer_id         BIGINT       NULL COMMENT '归并后回填',
    full_name           VARCHAR(100) NULL,
    gender              VARCHAR(16)  NULL,
    age                 INT          NULL,
    education_level     VARCHAR(32)  NULL,
    major               VARCHAR(100) NULL,
    work_years          INT          NULL,
    industry            VARCHAR(64)  NULL,
    position_title      VARCHAR(100) NULL,
    city                VARCHAR(64)  NULL,
    income_level        VARCHAR(32)  NULL,
    target_product_code VARCHAR(32)  NULL,
    phone_ciphertext    VARBINARY(512) NULL COMMENT '电话密文，不存明文',
    phone_lookup_token  VARCHAR(64)  NULL COMMENT '电话检索 token',
    contact_email       VARCHAR(254) NULL COMMENT '本期仅受控掩码或 NULL',
    raw_fields          JSON         NULL,
    row_version         INT          NOT NULL DEFAULT 1,
    created_at          DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_source (source_id),
    KEY idx_lookup (phone_lookup_token)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS research_rule (
    id              BIGINT NOT NULL AUTO_INCREMENT,
    product_id      BIGINT      NOT NULL,
    rule_version    VARCHAR(32) NOT NULL COMMENT '不可变版本',
    rule_content    JSON        NOT NULL,
    rule_description TEXT       NULL,
    is_active       TINYINT(1)  NOT NULL DEFAULT 0,
    active_slot     SMALLINT    NULL COMMENT '单产品单生效槽',
    effective_from  DATETIME    NULL,
    effective_to    DATETIME    NULL,
    created_by      BIGINT      NULL,
    row_version     INT         NOT NULL DEFAULT 1,
    created_at      DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_product_version (product_id, rule_version)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS research_result (
    id                  BIGINT NOT NULL AUTO_INCREMENT,
    source_id           BIGINT       NOT NULL,
    customer_info_id    BIGINT       NOT NULL,
    product_id          BIGINT       NOT NULL,
    rule_version        VARCHAR(32)  NOT NULL COMMENT '真实规则版本',
    input_snapshot      JSON         NULL COMMENT '受保护输入快照',
    matched             TINYINT(1)   NOT NULL,
    matched_fields      JSON         NULL,
    unmatched_reasons   JSON         NULL,
    score               DECIMAL(5,2) NULL,
    created_by          BIGINT       NULL,
    created_at          DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_info (customer_info_id),
    KEY idx_product (product_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
