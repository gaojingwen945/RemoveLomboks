# RemoveLomboks

> 项目运行环境：python 3.6
>
> 调用示例：
>
> 默认不保存修改到文件：python3 remove_the_lomboks.py lombok_test_dir（源码路径） 
>
> 保存修改到文件：python3 remove_the_lomboks.py lombok_test_dir 1
>
> 保存修改到文件，并打开debug模式：python3 remove_the_lomboks.py lombok_test_dir 1 1

目前我们的Android工程中引用的org.projectlombok:lombok库（主要用于通过注解为data类自动生成getter/setter方法），对gradle build plugin 3.2.1+以上的kapt以及annotationProcessor支持都非常不友好，stackoverflow及github上都能找到相关的issue。

这个问题导致我们无法升级gradle build plugin版本，且考虑到lombok用处也并不是特别大，因此最近考虑将lombok库从项目中移除。

然鹅。。搜一搜项目中引用lombok的类：

![](pic/lombok_Data_refs.png)

可怕。。

好几百个类，这还只是引用lombok.Data的。

所以，为了不让自己眼睛瞎掉，我们先来想想，怎么用自动化批量修改的方式，来做这个事情。

参考人工修改的逻辑，思路大致如下：

1. @Data

- [x] ~~为了避免有重名的类，导致替换出错，先扫一遍看有import lombok的类是否有重名的，如果没有，直接替换，否则要手动检查~~ --> 更新：有重名的lombok类其实没事儿，只要所有的lombok类全都处理了*

- [x] 处理有import lombok.Data的类，

- 删掉import lombok.Data;那一行，

- 删掉@Data那一行，

- 将其所有属性都修改为public，

- 将调用本类（即前一个字符为空格）的setXxx(...)都替换为this.xxx = ... ，

- ~~（暂未发现调用本类getter方法的地方，先不考虑）~~

- 记住包名和类名 a.b.c.DataA；

- [x] 遍历指定目录下的所有文件，查找有import a.b.c.DataA的类，或者和DataA在同一目录下、并有直接引用DataA的类；

- [x] 在找到的类中，找到类型为DataA的变量名dataA，把dataA.isXxx、dataA.getXxx都替换成dataA.xxx，将dataA.setXxx替换为 dataA.xxx=... 。

2. @Setter

3. @Getter

4. @EqualsAndHashCode

===========================

备注：

目前已完成@Data的相关处理，需要注意：批处理脚本并不能完全代替人工，存在以下无法处理的情况：

1、调用父类方法，返回Lombok类的；

2、没有直接声明为Lombok类类型的：list.get(i).getXxx()。

因此使用时，最好一次只扫描固定数量（比如50个）的文件，如果有未处理、导致编译失败的情况，先手动进行处理，然后再进行下一批扫描。脚本当前默认扫描文件数用MAX_TOTAL_COUNT定义，目前是1000，可以根据自己的情况修改。



