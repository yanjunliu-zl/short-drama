import React, { useState } from 'react';
import {
  Card,
  Form,
  Input,
  Button,
  Select,
  Divider,
  Typography,
  Space,
  message,
  Row,
  Col,
  InputNumber,
  Upload,
} from 'antd';
import {
  SettingOutlined,
  SaveOutlined,
  ReloadOutlined,
  VideoCameraOutlined,
  FileOutlined,
  CloudUploadOutlined,
  UploadOutlined,
} from '@ant-design/icons';

const { Title, Text } = Typography;
const { Option, OptGroup } = Select;

const Settings: React.FC = () => {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);

  // 模拟加载设置
  const loadSettings = () => {
    const mockSettings = {
      videoRatio: '16:9',
      creationMode: 'ai',
      styleReference: [],
      notifications: true,
      autoSave: true,
    };
    form.setFieldsValue(mockSettings);
  };

  React.useEffect(() => {
    loadSettings();
  }, []);

  const handleSave = async (values: any) => {
    setLoading(true);
    try {
      // 模拟 API 调用
      await new Promise((resolve) => setTimeout(resolve, 800));
      console.log('保存设置:', values);
      message.success('设置保存成功');
    } catch (error) {
      message.error('保存失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    form.resetFields();
    loadSettings();
    message.info('设置已重置');
  };

  // 视频比例选项
  const videoRatioOptions = [
    { value: '16:9', label: '16:9 (横向视频)' },
    { value: '9:16', label: '9:16 (竖向视频)' },
    { value: '1:1', label: '1:1 (方形视频)' },
    { value: '4:3', label: '4:3 (传统比例)' },
  ];

  // 创作模式选项
  const creationModeOptions = [
    { value: 'ai', label: 'AI生成 (自动创建剧本和分镜)' },
    { value: 'assist', label: 'AI辅助 (用户主导，AI辅助优化)' },
    { value: 'manual', label: '手动创作 (完全手动创建)' },
  ];

  // 风格参考选项
  const styleCategories = [
    {
      label: '写实',
      options: [
        '古风写实', '真人写实', '古风明艳', '都市情感', '玄幻修仙',
        '现代末日', '赛博朋克', '悬疑恐怖', '东方历史战争', '未来科幻',
        '纪实摄影', '民国风格', '职场商场', '家庭伦理', '乡土风格',
        '律政法庭', '医疗救援', '80年代', '北欧极简', '古风唐朝',
        '古风宋朝', '古风明朝', '古风清朝'
      ]
    },
    {
      label: '动漫',
      options: [
        '3D东方仙侠', '3D国风正剧', '2D都市言情', 'CG武侠', '3D赛博朋克',
        '2D古风', '日漫', '皮克斯风格', '3D Q版', '儿童绘本',
        '国风水墨画', '3D奇幻史诗', '2D悬疑动漫', '毛绒质感', '赛璐璐',
        '手绘水彩', '扁片插画', '手帐风', '敦煌壁画风', '宫崎骏',
        '新海诚', '木叶隐村', '儿童科普(手绘风)'
      ]
    }
  ];

  // 风格参考上传处理
  const handleUpload = (info: any) => {
    const { status } = info.file;
    if (status === 'done') {
      message.success(`${info.file.name} 上传成功`);
    } else if (status === 'error') {
      message.error(`${info.file.name} 上传失败`);
    }
  };

  return (
    <div style={{ padding: '24px' }}>
      <div style={{ marginBottom: 24 }}>
        <Title level={2}>
          <SettingOutlined style={{ marginRight: 12 }} />
          概览
        </Title>
        <Text type="secondary">配置视频比例、创作模式及风格参考</Text>
      </div>

      <Form
        form={form}
        layout="vertical"
        onFinish={handleSave}
        initialValues={{
          videoRatio: '16:9',
          creationMode: 'ai',
          styleReference: [],
          notifications: true,
          autoSave: true,
        }}
      >
        <Row gutter={[24, 24]}>
          {/* 视频比例设置 */}
          <Col xs={24} lg={12}>
            <Card title="视频比例" size="small" extra={<VideoCameraOutlined />}>
              <Form.Item
                label="选择比例"
                name="videoRatio"
                rules={[{ required: true, message: '请选择视频比例' }]}
              >
                <Select placeholder="请选择视频比例">
                  {videoRatioOptions.map((opt) => (
                    <Option key={opt.value} value={opt.value}>
                      {opt.label}
                    </Option>
                  ))}
                </Select>
              </Form.Item>
              <Form.Item
                label="画质设置"
                name="videoQuality"
                initialValue="1080p"
              >
                <Select>
                  <Option value="4k">4K (3840x2160)</Option>
                  <Option value="1080p">Full HD (1920x1080)</Option>
                  <Option value="720p">HD (1280x720)</Option>
                  <Option value="480p">SD (854x480)</Option>
                </Select>
              </Form.Item>
              <Form.Item
                label="帧率"
                name="frameRate"
                initialValue={30}
              >
                <Select>
                  <Option value={24}>24 fps (电影感)</Option>
                  <Option value={30}>30 fps (标准)</Option>
                  <Option value={60}>60 fps (流畅)</Option>
                </Select>
              </Form.Item>
            </Card>
          </Col>

          {/* 创作模式设置 */}
          <Col xs={24} lg={12}>
            <Card title="创作模式" size="small" extra={<FileOutlined />}>
              <Form.Item
                label="选择模式"
                name="creationMode"
                rules={[{ required: true, message: '请选择创作模式' }]}
              >
                <Select placeholder="选择创作模式">
                  {creationModeOptions.map((opt) => (
                    <Option key={opt.value} value={opt.value}>
                      {opt.label}
                    </Option>
                  ))}
                </Select>
              </Form.Item>
              <Form.Item
                label="AI角色数量"
                name="aiCharacterCount"
                initialValue={2}
              >
                <InputNumber min={1} max={10} style={{ width: '100%' }} />
              </Form.Item>
              <Form.Item
                label="剧本长度（分钟）"
                name="scriptLength"
                initialValue={5}
              >
                <InputNumber min={1} max={60} style={{ width: '100%' }} />
              </Form.Item>
            </Card>
          </Col>
        </Row>

        {/* 风格参考 */}
        <Card title="风格参考" size="small" style={{ marginTop: 24 }} extra={<CloudUploadOutlined />}>
          <Form.Item label="风格类别" name="styleCategory">
            <Select placeholder="选择风格类别">
              {styleCategories.map((cat) => (
                <OptGroup key={cat.label} label={cat.label}>
                  {cat.options.map((opt) => (
                    <Option key={opt} value={opt}>
                      {opt}
                    </Option>
                  ))}
                </OptGroup>
              ))}
            </Select>
          </Form.Item>
          <Form.Item label="参考图片" name="styleReference">
            <Upload
              action="/api/upload"
              listType="picture-card"
              maxCount={5}
              onChange={handleUpload}
            >
              <div>
                <UploadOutlined />
                <div style={{ marginTop: 8 }}>上传参考</div>
              </div>
            </Upload>
          </Form.Item>
          <Form.Item label="风格描述" name="styleDescription">
            <Input.TextArea
              placeholder="描述你想要的视频风格，例如：现代简约、复古胶片、赛博朋克等"
              rows={3}
            />
          </Form.Item>
        </Card>

        <Divider />

        <div style={{ textAlign: 'right', marginTop: 24 }}>
          <Space>
            <Button
              icon={<ReloadOutlined />}
              onClick={handleReset}
              disabled={loading}
            >
              重置
            </Button>
            <Button
              type="primary"
              icon={<SaveOutlined />}
              htmlType="submit"
              loading={loading}
            >
              保存设置
            </Button>
          </Space>
        </div>
      </Form>
    </div>
  );
};

export default Settings;
