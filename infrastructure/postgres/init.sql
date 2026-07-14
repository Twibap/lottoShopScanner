CREATE TABLE IF NOT EXISTS draw_results (
    draw INTEGER PRIMARY KEY CHECK (draw > 0),
    draw_date DATE NOT NULL,
    first_winner_count INTEGER NOT NULL CHECK (first_winner_count >= 0),
    first_prize BIGINT NOT NULL CHECK (first_prize >= 0),
    first_total_prize BIGINT NOT NULL CHECK (first_total_prize >= 0),
    second_winner_count INTEGER NOT NULL CHECK (second_winner_count >= 0),
    second_prize BIGINT NOT NULL CHECK (second_prize >= 0),
    second_total_prize BIGINT NOT NULL CHECK (second_total_prize >= 0),
    raw_data JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS shops (
    shop_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    address TEXT NOT NULL,
    region TEXT NOT NULL,
    phone TEXT,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    latest_draw INTEGER NOT NULL CHECK (latest_draw > 0),
    raw_data JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS winning_events (
    draw INTEGER NOT NULL REFERENCES draw_results(draw) ON DELETE CASCADE,
    event_sequence INTEGER NOT NULL CHECK (event_sequence > 0),
    shop_id TEXT NOT NULL REFERENCES shops(shop_id),
    prize_rank SMALLINT NOT NULL CHECK (prize_rank IN (1, 2)),
    prize_amount BIGINT NOT NULL CHECK (prize_amount >= 0),
    win_method TEXT,
    raw_data JSONB NOT NULL,
    PRIMARY KEY (draw, event_sequence)
);

CREATE INDEX IF NOT EXISTS winning_events_shop_id_idx ON winning_events (shop_id);
CREATE INDEX IF NOT EXISTS winning_events_rank_idx ON winning_events (prize_rank, shop_id);

CREATE TABLE IF NOT EXISTS shop_statistics (
    shop_id TEXT PRIMARY KEY REFERENCES shops(shop_id) ON DELETE CASCADE,
    first_count INTEGER NOT NULL,
    second_count INTEGER NOT NULL,
    first_prize BIGINT NOT NULL,
    second_prize BIGINT NOT NULL,
    total_prize BIGINT NOT NULL,
    winning_draw_count INTEGER NOT NULL,
    last_winning_draw INTEGER NOT NULL,
    first_rank INTEGER NOT NULL,
    second_rank INTEGER NOT NULL,
    total_prize_rank INTEGER NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS shop_statistics_first_rank_idx ON shop_statistics (first_rank, shop_id);
CREATE INDEX IF NOT EXISTS shop_statistics_second_rank_idx ON shop_statistics (second_rank, shop_id);
CREATE INDEX IF NOT EXISTS shop_statistics_total_prize_rank_idx
    ON shop_statistics (total_prize_rank, shop_id);
